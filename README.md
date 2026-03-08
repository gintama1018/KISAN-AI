<div align="center">

<img src="https://img.shields.io/badge/🌾_KISAN_AI-Real--Time_Farm_Intelligence-2ea44f?style=for-the-badge&labelColor=1a7f37" alt="Kisan AI" height="50"/>

# KISAN AI
### Real-Time Satellite-Powered Agricultural Intelligence for India's 120M Smallholder Farmers

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Gemini](https://img.shields.io/badge/Gemini_2.5_Flash-AI_Advisory-4285F4?style=flat-square&logo=google&logoColor=white)](https://aistudio.google.com)
[![ElevenLabs](https://img.shields.io/badge/ElevenLabs-Voice_TTS-000000?style=flat-square&logo=elevenlabs&logoColor=white)](https://elevenlabs.io)
[![Twilio](https://img.shields.io/badge/Twilio-WhatsApp_Delivery-F22F46?style=flat-square&logo=twilio&logoColor=white)](https://twilio.com)
[![NASA](https://img.shields.io/badge/NASA_POWER-Satellite_Data-E03C31?style=flat-square&logo=nasa&logoColor=white)](https://power.larc.nasa.gov)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

<br/>

> **"40% of Indian farmers are illiterate. A WhatsApp text does nothing. A voice message in their own dialect does everything."**

<br/>

[🚀 Quick Start](#-quick-start) · [🏗️ Architecture](#️-architecture) · [🛰️ Data Sources](#️-data-sources) · [🤖 AI Pipeline](#-ai-pipeline) · [📡 API Reference](#-api-reference) · [🗺️ Demo](#️-live-demo)

</div>

---

## 🌍 The Problem We're Solving

India has **120 million smallholder farmers** farming plots under 2 hectares. Every year:

- 🌧️ **Delayed monsoon warnings** destroy crops worth ₹2.7 lakh crore
- 🐛 **Undetected pest outbreaks** spread silently across 30% of crop area
- 💧 **Over-irrigation in droughts** wastes water, burns crops
- 📱 **Existing apps require literacy** — SMS, text-heavy dashboards fail rural India
- 🕐 **Government advisories arrive 48–72 hours late**, via broadcast radio

**KISAN AI** solves all of this: sub-hour satellite data → AI analysis → voice advisory → WhatsApp delivery. In their language. Before the damage is done.

---

## 🏗️ Architecture

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         KISAN AI — SYSTEM ARCHITECTURE                       ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║   ┌─────────────────────────────────────────────────────────────────────┐    ║
║   │                    LAYER 1 — DATA INGESTION                         │    ║
║   │                                                                      │    ║
║   │  🛰️ NASA POWER API         🌡️ Open-Meteo API     🗺️ ISRO Bhuvan WMS │    ║
║   │  (solar radiation,         (real-time temp,        (NDVI, land use,  │    ║
║   │   evapotranspiration,       humidity, wind,         soil type maps)  │    ║
║   │   soil moisture)            precipitation)                           │    ║
║   │           │                       │                       │          │    ║
║   │           └───────────────────────┼───────────────────────┘          │    ║
║   │                                   ▼                                   │    ║
║   │                      data/satellite.py                                │    ║
║   │                   (unified fetch + geocoding)                         │    ║
║   └────────────────────────────┬─────────────────────────────────────────┘    ║
║                                │                                               ║
║                                ▼                                               ║
║   ┌─────────────────────────────────────────────────────────────────────┐    ║
║   │                    LAYER 2 — STREAMING ENGINE                        │    ║
║   │                                                                      │    ║
║   │          pipeline/stream.py  (Pathway real-time processor)           │    ║
║   │                                                                      │    ║
║   │   Raw JSON ──► normalize ──► threshold_check ──► alert_emit         │    ║
║   │   (JSONL)       (units)       (per-crop rules)     (JSONL out)       │    ║
║   │                                                                      │    ║
║   │   ⚡ Sub-30s latency  |  30-min cache TTL  |  55 villages indexed   │    ║
║   └────────────────────────────┬─────────────────────────────────────────┘    ║
║                                │                                               ║
║                                ▼                                               ║
║   ┌─────────────────────────────────────────────────────────────────────┐    ║
║   │                      LAYER 3 — AI MODELS                            │    ║
║   │                                                                      │    ║
║   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │    ║
║   │  │ drought.py   │  │   pest.py    │  │       sowing.py          │  │    ║
║   │  │              │  │              │  │                          │  │    ║
║   │  │ Soil moisture│  │ NDVI drop +  │  │  Temperature + rainfall  │  │    ║
║   │  │ + ET0 stress │  │ humidity +   │  │  window calculator for   │  │    ║
║   │  │   scoring    │  │ temp bands   │  │  optimal sowing dates    │  │    ║
║   │  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘  │    ║
║   │         │                 │                       │                  │    ║
║   │         └─────────────────┼───────────────────────┘                  │    ║
║   │                           ▼                                           │    ║
║   │                    ✨ ai/gemini.py                                    │    ║
║   │              Gemini 2.5 Flash — Expert agronomist LLM                │    ║
║   │         (satellite data → natural language advisory in 10 languages) │    ║
║   └────────────────────────────┬─────────────────────────────────────────┘    ║
║                                │                                               ║
║                                ▼                                               ║
║   ┌─────────────────────────────────────────────────────────────────────┐    ║
║   │                  LAYER 4 — MULTILINGUAL OUTPUT                       │    ║
║   │                                                                      │    ║
║   │   ai/translate.py                        ai/voice.py                 │    ║
║   │   ┌────────────────────────────┐         ┌───────────────────────┐  │    ║
║   │   │ 10 Indian languages:       │         │ ElevenLabs            │  │    ║
║   │   │ Hindi · Marathi · Tamil    │         │ eleven_multilingual_v2│  │    ║
║   │   │ Telugu · Bengali · Kannada │─────────► MP3 voice advisory    │  │    ║
║   │   │ Punjabi · Gujarati · Odia  │         │ (494 KB avg per alert)│  │    ║
║   │   │ + phrase bank (offline)    │         └──────────┬────────────┘  │    ║
║   │   └────────────────────────────┘                    │               │    ║
║   └─────────────────────────────────────────────────────┼───────────────┘    ║
║                                                          │                     ║
║                                                          ▼                     ║
║   ┌─────────────────────────────────────────────────────────────────────┐    ║
║   │                    LAYER 5 — DELIVERY                                │    ║
║   │                                                                      │    ║
║   │   📱 Twilio WhatsApp          🗺️ Leaflet Map          📊 Dashboard  │    ║
║   │                                                                      │    ║
║   │   MP3 → Twilio Assets CDN     Village heatmap        Chart.js        │    ║
║   │   → WhatsApp voice note       (drought/pest/sow)     risk graphs     │    ║
║   │   to farmer's phone           real-time SSE stream                   │    ║
║   │                                                                      │    ║
║   │   ✅ No app install needed    ✅ Works on basic smartphones          │    ║
║   │   ✅ No literacy required     ✅ Sub-60s end-to-end latency          │    ║
║   └─────────────────────────────────────────────────────────────────────┘    ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

---

## 🔄 End-to-End Request Flow

```
Farmer's village
      │
      │  (name + crop + language)
      ▼
┌─────────────────┐     cache hit      ┌──────────────────┐
│   Flask API     │──────────────────► │  In-Memory Cache │
│   app.py        │                    │  (30-min TTL)    │
└────────┬────────┘                    └──────────────────┘
         │ cache miss
         ▼
┌─────────────────┐
│  Geocode village│  ◄── Nominatim / OSM
│  → (lat, lon)   │
└────────┬────────┘
         │
         ├────────────────────────────────────────┐
         ▼                                        ▼
┌─────────────────┐                    ┌──────────────────┐
│  Open-Meteo API │                    │  NASA POWER API  │
│  (real-time)    │                    │  (historical +   │
│  temp, humidity │                    │   solar rad,     │
│  wind, rain     │                    │   evapotransp.)  │
└────────┬────────┘                    └────────┬─────────┘
         │                                      │
         └──────────────┬───────────────────────┘
                        ▼
              ┌──────────────────┐
              │  compute_ndvi()  │
              │  (NDVI from LSWI │
              │   + optical bands│
              └────────┬─────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
  ┌────────────┐ ┌──────────┐ ┌──────────────┐
  │ drought.py │ │ pest.py  │ │  sowing.py   │
  │ risk score │ │ risk +   │ │  window dict │
  │  0–100     │ │ pest name│ └──────┬───────┘
  └─────┬──────┘ └────┬─────┘        │
        └─────────────┼──────────────┘
                      ▼
             ┌─────────────────┐
             │  gemini.py      │
             │  Gemini 2.5 FL  │
             │  → NL advisory  │
             │  in target lang │
             └────────┬────────┘
                      │
         ┌────────────┼────────────────┐
         ▼            ▼                ▼
  ┌───────────┐ ┌───────────┐  ┌──────────────┐
  │ JSON resp │ │ translate │  │  voice.py    │
  │ to browser│ │  .py      │  │  ElevenLabs  │
  │ dashboard │ │ 10 langs  │  │  → MP3       │
  └───────────┘ └───────────┘  └──────┬───────┘
                                       │
                               ┌───────▼──────────┐
                               │  Twilio Assets   │
                               │  CDN upload      │
                               │  (*.twil.io URL) │
                               └───────┬──────────┘
                                       │
                               ┌───────▼──────────┐
                               │  WhatsApp voice  │
                               │  note to farmer  │
                               │  📱 delivered    │
                               └──────────────────┘
```

---

## 🛰️ Data Sources

| Source | Data | Key Required | Latency |
|--------|------|:------------:|---------|
| **NASA POWER API** | Soil moisture, evapotranspiration, solar radiation, wind | ❌ Free | ~2 day lag (historical) |
| **Open-Meteo API** | Temperature, humidity, precipitation, wind speed | ❌ Free | Real-time |
| **ISRO Bhuvan WMS** | NDVI, land use, soil type layers | ❌ Free (basic) | Daily |
| **AgroMonitoring** | Enhanced NDVI (Sentinel-2), crop health | ⚠️ Optional (60/day free) | Daily |
| **Nominatim / OSM** | Village geocoding (lat/lon) | ❌ Free | On-demand |

> **Zero mandatory API keys for satellite data.** The entire data pipeline runs free.

---

## 🤖 AI Pipeline

### Gemini 2.5 Flash — Advisory Engine

```python
# Example prompt structure (automatically generated per village)
"""
You are an expert Indian agricultural scientist with 20 years experience.

Farmer in Nashik, Maharashtra grows grapes. Today: March 8 (Rabi harvest season).

LIVE SATELLITE DATA (NASA + ISRO):
- Soil Moisture:       8.1%          ← CRITICAL: below 10% threshold
- NDVI (greenness):    0.394         ← moderate stress
- Rainfall (7 days):   0.0 mm        ← drought conditions
- Temperature max:     37.3°C        ← heat stress territory
- Humidity:            61%
- Evapotranspiration:  6.19 mm/day   ← very high water loss

Advisory: 3 sentences in Hindi. Address farmer as 'किसान भाई'. 
Specific action to take TODAY.
"""

# Output (actual Gemini response):
# किसान भाई, बढ़ती गर्मी और मिट्टी में नमी की भारी कमी के कारण
# आपके अंगूर के दाने सिकुड़ सकते हैं।
# आज शाम को ही ड्रिप से हल्की सिंचाई करें।
```

**Model fallback chain**: `gemini-2.5-flash` → `gemini-2.0-flash` → `gemini-flash-latest`

### Rule-Based Models (Pre-Gemini Fallback)

| Model | Algorithm | Input Features | Output |
|-------|-----------|----------------|--------|
| `drought.py` | Weighted risk score + per-crop thresholds | Soil moisture, ET₀, rainfall 7d, temp | Score 0–100, severity label |
| `pest.py` | NDVI drop detection + temperature-humidity bands | NDVI Δ, humidity, temp, rainfall | Risk level + pest name |
| `sowing.py` | Phenological window calculator | Temp, soil temp, rainfall patterns | Optimal sowing date range |

### Supported Languages (10 Indian Languages)

| Code | Language | Script | Farmers covered |
|------|----------|--------|-----------------|
| `hi` | **Hindi** | Devanagari | 52 crore |
| `mr` | **Marathi** | Devanagari | 8.3 crore |
| `ta` | **Tamil** | Tamil | 7.5 crore |
| `te` | **Telugu** | Telugu | 8.2 crore |
| `bn` | **Bengali** | Bengali | 10.7 crore |
| `kn` | **Kannada** | Kannada | 4.4 crore |
| `pa` | **Punjabi** | Gurmukhi | 3.3 crore |
| `gu` | **Gujarati** | Gujarati | 5.5 crore |
| `or` | **Odia** | Odia | 3.8 crore |
| `en` | **English** | Latin | — |

---

## 🗺️ Live Demo

### Dashboard
The web dashboard (`/`) shows:
- **Interactive Leaflet map** — all 55 villages with colour-coded risk markers
- **Real-time satellite readings** — soil moisture, NDVI, temperature
- **AI advisory panel** — Gemini-generated advice in selected language
- **Risk trend charts** — drought / pest / sowing scores over time (Chart.js)
- **Language selector** — switch language, advisory re-renders instantly

### Villages Covered (55 across India)

```
Maharashtra:  Nashik · Pune · Nagpur · Aurangabad · Solapur
Uttar Pradesh: Varanasi · Allahabad · Lucknow · Agra · Kanpur
Andhra Pradesh: Anantapur · Kurnool · Guntur · Nellore
Tamil Nadu:   Coimbatore · Madurai · Salem · Tirunelveli
Punjab:       Amritsar · Ludhiana · Patiala · Bathinda
Rajasthan:    Jaipur · Jodhpur · Bikaner · Kota
... and more
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+ (tested on 3.14.3)
- Windows / Linux / macOS

### 1. Clone & Install

```bash
git clone https://github.com/gintama1018/KISAN-AI.git
cd "KISAN-AI"

# Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Linux / Mac
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` — only **3 keys are needed** for full AI + voice functionality:

```env
# ── Required for AI advisory ──────────────────────────────────────────
GEMINI_API_KEY=your_key         # Free at aistudio.google.com/app/apikey

# ── Required for voice alerts ─────────────────────────────────────────
ELEVENLABS_API_KEY=your_key     # Free tier: 10,000 chars/month — elevenlabs.io
ELEVENLABS_VOICE_ID=your_id     # Choose any voice from ElevenLabs library

# ── Required for WhatsApp delivery ────────────────────────────────────
TWILIO_ACCOUNT_SID=ACxxxx       # Free trial at twilio.com
TWILIO_AUTH_TOKEN=xxxx
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# ── NASA + Open-Meteo: NO KEY NEEDED ───────────────────────────────────
```

### 3. Run

```bash
# Windows
run.bat

# Linux / Mac
chmod +x run.sh && ./run.sh

# Or directly
python app.py
```

Open **http://localhost:5000** — the dashboard is live.

---

## 📡 API Reference

### `GET /api/village`

Fetch real-time satellite data + AI advisory for a village.

```bash
GET /api/village?name=Nashik&state=Maharashtra&crop=grapes&lang=hi
```

**Response:**
```json
{
  "village": "Nashik",
  "crop": "grapes",
  "lang": "hi",
  "soil_moisture": 8.1,
  "ndvi": 0.394,
  "temp_max": 37.3,
  "humidity": 61,
  "rainfall_7d": 0.0,
  "et0": 6.19,
  "drought": {
    "risk_score": 82,
    "severity": "critical",
    "recommendation": "Irrigate immediately"
  },
  "pest": {
    "risk_level": "medium",
    "pest_name": "thrips",
    "recommendation": "Monitor; spray neem oil if confirmed"
  },
  "sowing": {
    "status": "not_applicable",
    "message": "Grapes are a perennial crop"
  },
  "gemini_advisory": "किसान भाई, बढ़ती गर्मी और मिट्टी में नमी की भारी कमी...",
  "gemini_source": "gemini",
  "model": "models/gemini-2.5-flash",
  "cached": false,
  "timestamp": "2026-03-08T04:00:13.347199"
}
```

### `GET /api/gemini`

Direct Gemini advisory (bypasses rule-based models).

```bash
GET /api/gemini?name=Nashik&crop=grapes&lang=mr
```

### `POST /api/voice`

Generate ElevenLabs voice + send WhatsApp voice note.

```bash
POST /api/voice
Content-Type: application/json

{
  "to": "+916377866035",
  "village": "Nashik",
  "crop": "grapes",
  "lang": "hi"
}
```

**Response:**
```json
{
  "status": "sent",
  "sid": "MM840dbe2e602d66ad3fc6d95df977358a",
  "type": "voice",
  "audio_url": "https://kisanai-8bcedbffd8f4.twil.io/kisan_8bcedbffd8f4.mp3",
  "chars_generated": 343
}
```

### `POST /api/voice/preview`

Generate MP3 locally without sending WhatsApp (for testing).

```bash
POST /api/voice/preview
Content-Type: application/json

{ "text": "आज सिंचाई करें।", "lang": "hi" }
```

### `GET /api/whatsapp`

Send text WhatsApp alert.

```bash
GET /api/whatsapp?name=Nashik&to=%2B916377866035&lang=hi
```

### `GET /api/villages`

List all 55 indexed villages with metadata.

### `GET /api/translate`

Translate any text to a supported Indian language.

```bash
GET /api/translate?text=Severe+drought+risk&lang=ta
```

### `GET /api/languages`

List all supported language codes.

### `GET /api/stream`

Server-Sent Events (SSE) stream — real-time alerts pushed to the browser dashboard.

### `GET /health`

Health check — returns loaded village count and system status.

---

## 📁 Project Structure

```
KISAN-AI/
│
├── 📄 app.py                  # Flask application — all routes, caching, SSE
│
├── 🤖 ai/
│   ├── gemini.py              # Gemini 2.5 Flash advisory engine
│   ├── voice.py               # ElevenLabs TTS + Twilio Assets + WhatsApp
│   ├── drought.py             # Drought risk scoring (rule-based)
│   ├── pest.py                # Pest detection model
│   ├── sowing.py              # Optimal sowing window calculator
│   └── translate.py           # 10-language translation (phrase bank + Google)
│
├── 📡 data/
│   ├── satellite.py           # NASA POWER + Open-Meteo unified fetcher
│   ├── ndvi.py                # NDVI computation from satellite bands
│   ├── villages.jsonl         # 55 Indian villages with lat/lon/crop/state
│   └── crop_thresholds.json   # Per-crop risk thresholds (wheat, rice, grapes…)
│
├── ⚡ pipeline/
│   └── stream.py              # Pathway real-time streaming engine
│
├── 🌐 static/
│   ├── map.js                 # Leaflet village map + risk heatmap
│   ├── style.css              # Dashboard styling
│   └── audio/                 # Generated MP3 voice alerts (git-ignored)
│
├── 📋 templates/
│   └── index.html             # Main dashboard (Leaflet + Chart.js + SSE)
│
├── ⚙️ .env.example             # Environment variable template
├── 📦 requirements.txt         # Python dependencies
├── 🖥️ run.bat                  # Windows launcher (auto-detects venv)
├── 🐧 run.sh                   # Linux/Mac launcher
└── 🔧 setup.ps1               # Windows first-time setup script
```

---

## 🔐 Security

| Concern | Mitigation |
|---------|-----------|
| API keys in version control | `.gitignore` blocks `.env` — keys never committed |
| Audio files in version control | `static/audio/` gitignored — generated at runtime |
| Twilio voice URLs guessable | URLs use MD5 hash of text — unguessable without content |
| Input injection | Village names validated against known list; query params sanitised |
| Cache poisoning | Thread-safe `threading.Lock` on all cache reads/writes |

> **Never paste API keys in chat, GitHub issues, or commit messages.** Always use `.env`.

---

## 📊 Performance

| Operation | Latency | Notes |
|-----------|---------|-------|
| Village satellite data | ~3–8 s | Cold fetch from NASA + Open-Meteo |
| Village advisory (cached) | < 50 ms | 30-min in-memory cache |
| Gemini advisory generation | ~2–4 s | 1M tokens/day free |
| ElevenLabs voice generation | ~8–15 s | 10,000 chars/month free |
| Twilio Assets upload + build | ~15–30 s | Cached per unique advisory |
| WhatsApp delivery | ~3–5 s | After asset is deployed |
| **End-to-end (cold)** | **~35–60 s** | |
| **End-to-end (warm cache)** | **< 15 s** | |

---

## � Voice Alerts — ElevenLabs → WhatsApp

This is KISAN AI's most impactful feature. Instead of sending a text message that 40% of farmers cannot read, the system generates a **natural-sounding voice note in the farmer's language** and delivers it as a **WhatsApp audio message** to their phone.

### How It Works — Step by Step

```
┌─────────────────────────────────────────────────────────────────────────────┐
│           VOICE ALERT PIPELINE — FULL FLOW                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STEP 1 — AI GENERATES ADVISORY                                             │
│  ─────────────────────────────────                                          │
│  Gemini 2.5 Flash reads live satellite data and writes:                     │
│                                                                             │
│  "किसान भाई, बढ़ती गर्मी और मिट्टी में नमी की भारी कमी के कारण           │
│   आपके अंगूर के दाने सिकुड़ सकते हैं। आज शाम को ड्रिप से                │
│   हल्की सिंचाई करें।"                                                      │
│                                │                                            │
│                                ▼                                            │
│  STEP 2 — ELEVENLABS CONVERTS TEXT TO VOICE                                 │
│  ───────────────────────────────────────────                                │
│  Model: eleven_multilingual_v2  (supports Hindi + all Indian languages)     │
│  Voice: Configurable (default: natural Indian-accented voice)               │
│  Output: MP3 file (~494 KB for a 3-sentence advisory)                       │
│  Cached: Yes — same advisory text reuses existing MP3                       │
│                                │                                            │
│                                ▼                                            │
│  STEP 3 — TWILIO ASSETS HOSTS THE AUDIO                                     │
│  ──────────────────────────────────────────                                 │
│  MP3 is uploaded to Twilio's own serverless CDN                             │
│  → No ngrok, no third-party hosting needed                                  │
│  → Twilio builds and deploys in ~15–30 seconds                              │
│  → Public HTTPS URL: https://kisanai-{hash}.twil.io/kisan_{hash}.mp3       │
│  → URL is cached locally so second send is instant                          │
│                                │                                            │
│                                ▼                                            │
│  STEP 4 — TWILIO SENDS WHATSAPP VOICE NOTE                                  │
│  ────────────────────────────────────────────                               │
│  Twilio API sends a WhatsApp message with:                                  │
│  • Body text: "🌾 Kisan AI — आपकी फसल के लिए आवाज़ सलाह सुनें:"            │
│  • media_url: the Twilio CDN MP3 link                                       │
│  → Farmer receives a playable audio note on WhatsApp                        │
│  → Works on ANY phone that has WhatsApp (no app install needed)             │
│  → No literacy required — just tap and listen                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### What the Farmer Receives on WhatsApp

```
┌─────────────────────────────────┐
│  📱  WhatsApp                   │
│  ─────────────────────────────  │
│                                 │
│  🌾  Kisan AI                   │
│  ──────────────                 │
│  🌾 Kisan AI — आपकी फसल के     │
│  लिए आवाज़ सलाह सुनें:          │
│                                 │
│  ┌───────────────────────────┐  │
│  │  🎵  ▶  ━━━━━━━━━━  0:12  │  │
│  └───────────────────────────┘  │
│  (tap to hear Hindi advisory)   │
│                                 │
│  ✓✓  08 Mar, 09:40 AM          │
└─────────────────────────────────┘
```

### Setting Up ElevenLabs (Free Tier — 10,000 chars/month)

**1. Get your API key:**
```
① Go to: https://elevenlabs.io
② Sign up (free)
③ Click your profile icon → top right
④ Click "API Key"
⑤ Copy the key
```

**2. Choose a voice (optional):**
```
① Go to: https://elevenlabs.io/voice-library
② Browse voices — filter by language "Hindi" for best results
③ Click any voice → "Add to VoiceLab"
④ Go to "VoiceLab" → copy the Voice ID
```

**3. Set in `.env`:**
```env
ELEVENLABS_API_KEY=your_api_key_here
ELEVENLABS_VOICE_ID=your_voice_id_here   # e.g. 56k72tYpS6hbRADdszYg
```

### Triggering a Voice Alert — 3 Ways

**Way 1 — REST API (programmatic):**
```bash
curl -X POST http://localhost:5000/api/voice \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+916377866035",
    "village": "Nashik",
    "crop": "grapes",
    "lang": "hi"
  }'
```

**Response:**
```json
{
  "status": "sent",
  "sid": "MM840dbe2e602d66ad3fc6d95df977358a",
  "type": "voice",
  "audio_url": "https://kisanai-8bcedbffd8f4.twil.io/kisan_8bcedbffd8f4.mp3",
  "chars_generated": 343
}
```

**Way 2 — Voice Preview (generate MP3 without sending, for testing):**
```bash
curl -X POST http://localhost:5000/api/voice/preview \
  -H "Content-Type: application/json" \
  -d '{"text": "आज सिंचाई करें।", "lang": "hi"}'
```
MP3 is saved to `static/audio/` and can be played locally.

**Way 3 — Python (directly from code):**
```python
from dotenv import load_dotenv; load_dotenv()
from ai.gemini import get_gemini_advisory
from ai.voice import send_whatsapp_voice

# 1. Get Gemini advisory
adv = get_gemini_advisory(
    village="Nashik", state="Maharashtra", crop="grapes",
    soil_moisture=8.1, ndvi=0.394, rainfall_7d=0.0,
    temp_max=37.3, humidity=61, et0=6.19,
    lang_code="hi"
)

# 2. Send as WhatsApp voice note
result = send_whatsapp_voice(
    advisory_text=adv["advisory"],
    to_number="+916377866035",   # farmer's WhatsApp number
    lang_code="hi",
)
print(result)
# → {'status': 'sent', 'sid': 'MM...', 'type': 'voice', 'audio_url': 'https://...'}
```

### Caching — Free Quota Protection

Every advisory text is hashed with MD5. If the same advisory was already generated (e.g. same village, same satellite conditions), the existing MP3 and Twilio CDN URL are reused instantly — **no ElevenLabs chars consumed, no rebuild needed**.

```
First call (cold):   15s ElevenLabs + 20s Twilio build = ~35s total
Second call (warm):  < 1s — served from local .url cache file
```

Cache files stored in `static/audio/`:
```
kisan_8bcedbffd8f4.mp3   ← audio file
kisan_8bcedbffd8f4.url   ← cached Twilio CDN URL
```

### Fallback Chain

If any step fails, the system degrades gracefully:

```
ElevenLabs TTS succeeds?
    YES → Twilio Assets upload → WhatsApp voice note  ✅
    NO  → Skip to text fallback

Twilio Assets upload succeeds?
    YES → WhatsApp voice note  ✅
    NO  → Try PUBLIC_BASE_URL (ngrok) if set

PUBLIC_BASE_URL set?
    YES → WhatsApp voice note via ngrok  ✅
    NO  → Send plain text WhatsApp message  📝
         (still useful, farmer reads or shows to someone)
```

The farmer always gets something — voice when possible, text when not.

---

## �🛠️ Tech Stack

```
┌──────────────────────────────────────────────────────────────────┐
│                        TECH STACK                                │
├─────────────────────┬────────────────────────────────────────────┤
│ Layer               │ Technology                                 │
├─────────────────────┼────────────────────────────────────────────┤
│ Web Framework       │ Flask 3.1 + Server-Sent Events (SSE)      │
│ Satellite Data      │ NASA POWER API + Open-Meteo (no key)      │
│ AI Advisory         │ Google Gemini 2.5 Flash (google-genai SDK)│
│ Voice TTS           │ ElevenLabs eleven_multilingual_v2         │
│ Translation         │ deep-translator (Google Translate wrapper) │
│ WhatsApp Delivery   │ Twilio WhatsApp + Twilio Assets CDN       │
│ Geocoding           │ Nominatim / OpenStreetMap                 │
│ Streaming Engine    │ Pathway (Linux/Docker) / Direct API mode  │
│ Frontend Map        │ Leaflet.js + OpenStreetMap tiles          │
│ Data Visualization  │ Chart.js                                  │
│ Data Processing     │ NumPy, Pandas, scikit-learn               │
│ Map Generation      │ Folium                                    │
│ Python Version      │ 3.10+ (tested on 3.14.3)                 │
└─────────────────────┴────────────────────────────────────────────┘
```

---

## 🌱 Roadmap

- [ ] **Pathway streaming** — Linux/Docker deployment for true real-time sub-second updates
- [ ] **ISRO Bhuvan NDVI** — direct GeoTIFF raster processing with rasterio
- [ ] **AgroMonitoring integration** — Sentinel-2 NDVI at 10m resolution
- [ ] **IVR voice calls** — for farmers without WhatsApp (Twilio Programmable Voice)
- [ ] **Crop disease image detection** — farmer sends photo → Gemini Vision diagnoses
- [ ] **Mandi price integration** — real-time AGMARKNET crop price advisories
- [ ] **Weather forecast integration** — 7-day forecast to predict pest windows
- [ ] **PWA mobile app** — offline-capable progressive web app
- [ ] **Production Docker deployment** — Gunicorn + Nginx + SSL

---

## 🤝 Contributing

Contributions welcome! Priority areas:
1. Adding more villages to `data/villages.jsonl`
2. Adding crop thresholds in `data/crop_thresholds.json`
3. Improving per-language TTS voice quality in `ai/voice.py`
4. Linux/Docker Pathway integration in `pipeline/stream.py`

```bash
# Fork, clone, create feature branch
git checkout -b feature/your-feature
# Make changes, test
python test_pipeline.py
# Submit PR
```

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ for India's farmers**

*Satellite data from NASA + ISRO · AI by Google Gemini · Voice by ElevenLabs · Delivery by Twilio*

<br/>

[![Made in India](https://img.shields.io/badge/Made_in-India_🇮🇳-FF9933?style=flat-square)](https://github.com/gintama1018/KISAN-AI)
[![For Farmers](https://img.shields.io/badge/For-120M_Farmers_🌾-2ea44f?style=flat-square)](https://github.com/gintama1018/KISAN-AI)

</div>
