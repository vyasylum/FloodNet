# ─────────────────────────────────────────────────────────────────────────────
# Flood-Net  –  FastAPI + Twilio webhook  →  Langflow  →  Neon Postgres
# (all fixes applied: await choose_closest_crew, no “zone” field, robust typing)
# ─────────────────────────────────────────────────────────────────────────────
import os, json, math, asyncio, logging, traceback
import asyncpg, httpx
from fastapi import FastAPI, Form, Response, status
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

# ── Logging & env ────────────────────────────────────────────────────────────
logging.basicConfig(
    filename="floodnet.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("floodnet")

load_dotenv()
DB_URL   = os.getenv("DB_URL")
FLOW_URL = os.getenv("FLOW_URL")
LF_TOKEN = os.getenv("LF_TOKEN")
assert all([DB_URL, FLOW_URL, LF_TOKEN]), ".env is missing keys"

# ── Globals ──────────────────────────────────────────────────────────────────
app    = FastAPI()
pool   = None
client = httpx.AsyncClient(timeout=15)

CREATE_CASES_SQL = """
CREATE TABLE IF NOT EXISTS cases (
  id        SERIAL PRIMARY KEY,
  phone     TEXT,
  raw_msg   TEXT,
  postcode  TEXT,
  people    INT,
  needs     JSONB,
  eta       INT,
  reply     TEXT,
  lat       FLOAT,
  lng       FLOAT,
  status    TEXT DEFAULT 'open',
  ts        TIMESTAMPTZ DEFAULT now()
)
"""

CREATE_CREWS_SQL = """
CREATE TABLE IF NOT EXISTS crews (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE,
  base_lat FLOAT,
  base_lng FLOAT
);
"""

# ── Startup / shutdown ───────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(DB_URL)
    async with pool.acquire() as con:
        await con.execute(CREATE_CASES_SQL)
        await con.execute(CREATE_CREWS_SQL)
        db = await con.fetchval("SELECT current_database()")
        log.info("DB connected → %s", db)

@app.on_event("shutdown")
async def shutdown():
    await client.aclose()
    await pool.close()

# ── Small helpers ────────────────────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    R, ϕ1, ϕ2 = 6371, math.radians(lat1), math.radians(lat2)
    dϕ  = ϕ2 - ϕ1
    dλ  = math.radians(lon2 - lon1)
    a   = math.sin(dϕ / 2)**2 + math.cos(ϕ1) * math.cos(ϕ2) * math.sin(dλ / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

async def choose_closest_crew(lat: float, lon: float) -> tuple[str, int]:
    """Return (crew_name, eta_minutes)"""
    rows = await pool.fetch("SELECT name, base_lat, base_lng FROM crews")
    if not rows:
        return "Unassigned", None
    # pick min distance
    crew, dist = min(
        ((r["name"], haversine(lat, lon, r["base_lat"], r["base_lng"])) for r in rows),
        key=lambda x: x[1],
    )
    eta = round(dist / 50 * 60)  # 50 km/h → minutes
    return crew, eta

async def postcode_to_latlon(pc: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"postalcode": pc, "country": "uk", "format": "json", "limit": 1}
    try:
        resp = await client.get(url, params=params, headers={"User-Agent": "FloodNet"})
        j = resp.json()
        if j:
            return float(j[0]["lat"]), float(j[0]["lon"])
    except Exception:
        pass
    return None

async def call_langflow(frm: str, body: str) -> dict:
    payload = {
        "input_value": json.dumps({"from": frm, "body": body}),
        "input_type": "text",
        "output_type": "text",
    }
    headers = {"Authorization": f"Bearer {LF_TOKEN}"}
    r = await client.post(FLOW_URL, json=payload, headers=headers)
    log.info("Langflow %s", r.status_code)
    r.raise_for_status()
    env = r.json()
    inner = (
        env["outputs"][0]["outputs"][0]["results"]["text"]["data"]["text"]
    )
    return json.loads(inner)

# ── Twilio webhook ───────────────────────────────────────────────────────────
@app.post("/twilio")
async def twilio_webhook(From: str = Form(...), Body: str = Form(...)):
    try:
        lf = await call_langflow(From, Body)
    except Exception as e:
        log.error("Langflow fail: %s", e, exc_info=True)
        lf = {"postcode": "", "people": 1, "needs": [], "reply":
              "🆘 Response: Request received – standby while we process."}

    postcode = lf.get("postcode", "")
    people   = lf.get("people", 1)
    needs    = lf.get("needs", [])
    reply    = lf["reply"]

    lat = lng = eta = None
    crew_name = "Unassigned"

    if postcode:
        coords = await postcode_to_latlon(postcode)
        if coords:
            lat, lng = coords
            crew_name, eta = await choose_closest_crew(lat, lng)
            if eta:
                reply = reply.replace("<ETA>", str(eta)).replace("ETA  min", f"ETA {eta} min")

    # write row
    try:
        async with pool.acquire() as con:
            await con.execute(
                """INSERT INTO cases
                   (phone, raw_msg, postcode, people, needs, eta, reply, lat, lng)
                   VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7,$8,$9)""",
                From, Body, postcode, people, json.dumps(needs),
                eta, reply, lat, lng
            )
    except Exception as e:
        log.error("DB insert failed: %s", e, exc_info=True)

    twiml = MessagingResponse(); twiml.message(reply)
    return Response(str(twiml), media_type="application/xml",
                    status_code=status.HTTP_200_OK)

# ── tiny liveness probe ──────────────────────────────────────────────────────
@app.get("/healthz", include_in_schema=False)
async def health():
    return {"status": "ok"}
