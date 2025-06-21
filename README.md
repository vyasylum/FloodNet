# 🛟 Flood-Net: AI-Assisted SOS Routing

> 🌊 From message to map in 5 seconds — AI-powered flood emergency coordination.

Flood-Net is a hackathon-ready system that triages WhatsApp SOS messages, parses free-text for key information using LLMs, assigns the nearest available rescue crew, and updates a real-time dashboard map — **no app install required.**

---

## 🧭 Key Features

- ✅ Twilio webhook receives WhatsApp messages
- 🤖 Langflow + Mistral parses location, people, needs, urgency
- 📍 FastAPI + Neon Postgres track incidents + assignments
- 🗺️ Streamlit dashboard shows live map with crew & case status
- 📦 Docker-ready, `.env` support, resilient to network drops

---

## 🗂️ Project Structure

flood-net/
├── .vscode/ # Editor config
├── pycache/ # Python cache
├── .env # Your environment variables (gitignored)
├── dashboard.py # Streamlit dashboard with map & controls
├── floodnet # Text notes or sample messages (optional)
├── server.py # FastAPI + Twilio webhook + LLM + routing
└── README.md # You're here!


---

## 🛠️ Tech Stack

| Layer         | Tool                        |
|---------------|-----------------------------|
| Messaging     | WhatsApp + Twilio           |
| Backend API   | FastAPI (async)             |
| Parsing       | Langflow + Mistral (LLM)    |
| Geocoding     | OpenStreetMap Nominatim     |
| Database      | Neon Postgres (hosted)      |
| Frontend      | Streamlit + Folium map      |
| Deployment    | Docker + Compose            |

---

## 🚀 Quickstart

Clone and Set Up

```bash
[git clone https://github.com/<your-org>/flood-net](https://github.com/vyasylum/FloodNe)
cd FloodNet
cp .env.example .env
```


📈 Future Plans
✅ Plug in Ordnance Survey API (UK-grade postcode lookup)

🌍 Multilingual LLM prompts (tested 1-shot Spanish 🇪🇸 + Bengali 🇧🇩)

📲 Flutter crew tablet view: reroute + chat

🔐 GDPR-compliant tokenization of phone numbers

🔄 Offline fallback with replayable logs (tail -f floodnet.log)


