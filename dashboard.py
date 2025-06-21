# dashboard.py ────────────────────────────────────────────────
import os, psycopg, pandas as pd, streamlit as st, requests, urllib.parse as u
from dotenv import load_dotenv
from streamlit_folium import st_folium
import folium, datetime as dt

load_dotenv()
DB_URL = os.getenv("DB_URL")

@st.cache_resource(show_spinner="🔌 Connecting to Neon…")
def get_conn():
    return psycopg.connect(DB_URL, autocommit=True)

def load_cases():
    q = """SELECT id,phone,postcode,people,needs,eta,status,reply,lat,lng
           FROM   cases ORDER BY id DESC LIMIT 200"""
    with get_conn().cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(q); return pd.DataFrame(cur.fetchall())

def postcode_to_latlon(pc:str):
    url = "https://nominatim.openstreetmap.org/search?" + \
          u.urlencode({"postalcode": pc, "country":"uk", "format":"json"})
    try:
        j = requests.get(url, headers={"User-Agent":"FloodNet"}).json()
        if j: return float(j[0]["lat"]), float(j[0]["lon"])
    except Exception: pass

st.set_page_config(page_title="Flood-Net Dashboard", layout="wide")
st.title("🛟 Flood-Net — Live SOS Dashboard")

df = load_cases()
if df.empty:
    st.info("No cases yet – send a WhatsApp to the bot.")
    st.stop()

# Add distance column if lat/lng exist
if df["lat"].notna().any():
    df["distance_km"] = (df["eta"].fillna(0) * 50 / 60).round(1)  # ≈50 km/h

status_filter = st.radio("Show:", ["Open only","All"], horizontal=True, index=0)
if status_filter == "Open only" and "status" in df.columns:
    df = df[df["status"].isna()]

def colour_rows(row):
    if "medical" in (row.needs or []):
        return ["background-color:#600d14"] * len(row)
    return [""] * len(row)

st.dataframe(
    df.style.apply(colour_rows, axis=1),
    column_config={"needs": st.column_config.JsonColumn()},
    use_container_width=True,
)


# ── Close case manually ───────────────────────────────────────
if not df.empty:
    cid = st.number_input("Mark ID rescued →", min_value=1, step=1)
    if st.button("Close case", use_container_width=True):
        with get_conn().cursor() as cur:
            cur.execute("UPDATE cases SET status='closed' WHERE id=%s", (cid,))
        st.success(f"Case {cid} closed."); st.experimental_rerun()

# ── Live map ──────────────────────────────────────────────────
good = df.dropna(subset=["lat","lng"])
if not good.empty:
    centre = [good["lat"].mean(), good["lng"].mean()]
    m = folium.Map(location=centre, zoom_start=6, tiles="cartodbpositron")
    for _, r in good.iterrows():
        col = "red" if pd.isna(r["status"]) else "green"
        popup = f"<b>Case {r.id}</b><br>{r.postcode}<br>ETA: {r.eta} min"
        folium.Marker([r.lat, r.lng],
                      tooltip=f"#{r.id} {r.postcode}",
                      popup=popup,
                      icon=folium.Icon(color=col)).add_to(m)
    st.markdown("### 🗺️  Live Incident Map")
    st_folium(m, width="100%", height=480)
else:
    st.info("Location data not available yet.")
