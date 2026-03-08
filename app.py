"""
app.py
------
KISAN AI — Flask Web Application

Serves the farmer dashboard and provides API endpoints.
Works in two modes:
  1. Live mode: reads Pathway output from /tmp/kisan_alerts.jsonl
  2. Direct mode: calls satellite APIs directly (no Pathway needed)

Start: python app.py
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from threading import Lock

from flask import Flask, jsonify, render_template, request, Response
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

load_dotenv()

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.satellite import fetch_all_satellite_data, geocode_village
from data.ndvi import fetch_ndvi
from data.accuracy import cross_validate
from ai.drought import drought_risk_model
from ai.pest import pest_risk_model
from ai.sowing import sowing_window_model
from ai.translate import translate_advisory, build_full_advisory, SUPPORTED_LANGUAGES
from ai.gemini import get_gemini_advisory, get_gemini_pest_analysis
from ai.voice import generate_voice_alert, send_whatsapp_voice

# ─────────────────────────────────────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "kisan-ai-dev-key")
# Trust Render / nginx reverse proxy headers so request.host_url is correct
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

ALERTS_FILE = os.getenv("ALERTS_FILE", "/tmp/kisan_alerts.jsonl")

# In-memory cache: village_key → {data, timestamp}
_cache: dict = {}
_cache_lock = Lock()
CACHE_TTL = 1800   # 30 minutes


# ─────────────────────────────────────────────────────────────────────────────
# Villages Index
# ─────────────────────────────────────────────────────────────────────────────

def load_villages_index() -> list:
    path = os.path.join(os.path.dirname(__file__), "data", "villages.jsonl")
    villages = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    villages.append(json.loads(line))
    except Exception as e:
        logger.warning("Could not load villages index: %s", e)
    return villages


VILLAGES_INDEX = load_villages_index()
VILLAGES_BY_NAME = {v["village_name"].lower(): v for v in VILLAGES_INDEX}


# ─────────────────────────────────────────────────────────────────────────────
# Core Advisory Builder — Direct Mode (no Pathway required)
# ─────────────────────────────────────────────────────────────────────────────

def build_village_advisory(lat: float, lon: float, village_name: str,
                           crop: str = "wheat", lang: str = "hi") -> dict:
    """
    Fetch satellite data, run AI models, and return a full advisory dict.
    This is the core function used by the Flask API.
    """
    cache_key = f"{lat:.4f},{lon:.4f},{crop}"
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and (time.time() - cached["_cached_at"]) < CACHE_TTL:
            logger.info("Cache hit for %s", village_name)
            # Deep-copy AI sub-dicts to avoid mutating the cached object
            import copy
            base = dict(cached)
            base["drought"] = dict(cached["drought"])
            base["pest"] = dict(cached["pest"])
            base["sowing"] = dict(cached["sowing"])
            base.pop("_cached_at", None)
            if lang != "hi":
                base["drought"]["action_translated"] = translate_advisory(
                    base["drought"]["action"], lang)
                base["pest"]["action_translated"] = translate_advisory(
                    base["pest"]["action"], lang)
            return base

    # Fetch data
    weather = fetch_all_satellite_data(lat, lon)
    ndvi_data = fetch_ndvi(lat, lon)

    # Run models
    drought = drought_risk_model(
        soil_moisture=weather["soil_moisture"],
        ndvi=ndvi_data["ndvi"],
        rainfall_7d=weather["rainfall_7d"],
        et0=weather["et0_today"],
        crop=crop,
        rainfall_deficit=weather.get("rainfall_deficit_7d", 0),
    )

    pest = pest_risk_model(
        temp_max=weather["temp_max"],
        temp_min=weather["temp_min"],
        humidity=weather["humidity"],
        ndvi=ndvi_data["ndvi"],
        ndvi_7d_ago=ndvi_data["ndvi_7d_ago"],
        crop=crop,
        rainfall_today=weather["rainfall_today"],
    )

    sowing = sowing_window_model(
        soil_temp=weather["soil_temp"],
        forecast_rainfall=weather.get("forecast_rainfall", []),
        et0=weather["et0_today"],
        soil_moisture=weather["soil_moisture"],
        crop=crop,
        current_rainfall=weather["rainfall_today"],
    )

    advisory_hi = build_full_advisory(
        drought=drought, pest=pest, sowing=sowing,
        lang_code="hi", village_name=village_name, crop=crop,
    )

    result = {
        "village": village_name,
        "crop": crop,
        "lat": lat,
        "lon": lon,
        "timestamp": weather["timestamp"],
        "data_source": weather.get("source", "open-meteo"),
        "ndvi_source": ndvi_data.get("source", "estimated"),

        # Current conditions
        "soil_moisture":    weather["soil_moisture"],
        "ndvi":             ndvi_data["ndvi"],
        "ndvi_7d_ago":      ndvi_data.get("ndvi_7d_ago", ndvi_data["ndvi"]),
        "ndvi_trend":       ndvi_data.get("ndvi_trend", "stable"),
        "rainfall_today":   weather["rainfall_today"],
        "rainfall_7d":      weather["rainfall_7d"],
        "et0":              weather["et0_today"],
        "temp_max":         weather["temp_max"],
        "temp_min":         weather["temp_min"],
        "humidity":         weather["humidity"],
        "current_temp":     weather.get("current_temp", weather["temp_max"]),
        "wind_speed":       weather.get("wind_speed", 10.0),
        "soil_temp":        weather.get("soil_temp", 22.0),

        # 7-day forecast arrays
        "forecast_dates":    weather.get("forecast_dates", []),
        "forecast_rainfall": weather.get("forecast_rainfall", []),
        "forecast_temp_max": weather.get("forecast_temp_max", []),
        "forecast_et0":      weather.get("forecast_et0", []),
        "forecast_humidity": weather.get("forecast_humidity", []),

        # AI model outputs
        "drought": drought,
        "pest": pest,
        "sowing": sowing,

        # Multilingual advisory (rule-based fallback)
        "advisory_hindi": advisory_hi,

        # Gemini AI advisory (intelligent, contextual) — populated below
        "gemini_advisory": "",
        "gemini_source": "not_configured",

        "_cached_at": time.time(),
    }

    # Gemini — call after cache store so slow calls don't block fast rule-based response
    state = ""
    for v in VILLAGES_INDEX:
        if v["village_name"].lower() == village_name.lower():
            state = v.get("state", "")
            break

    # Cross-validation confidence score (Layer 3)
    nasa_data = {k: weather.get(k) for k in
                 ("source", "avg_daily_rainfall_30d", "total_rainfall_30d",
                  "avg_temp_30d", "rainfall_history")}
    accuracy = cross_validate(weather, nasa_data, ndvi_data)
    result["accuracy_confidence"] = accuracy["confidence"]
    result["accuracy_warnings"]   = accuracy["warnings"]
    result["rain_validated"]      = accuracy["rain_final"]

    gemini = get_gemini_advisory(
        village=village_name, state=state, crop=crop,
        soil_moisture=weather["soil_moisture"],
        ndvi=ndvi_data["ndvi"],
        rainfall_7d=weather["rainfall_7d"],
        temp_max=weather["temp_max"],
        humidity=weather["humidity"],
        et0=weather["et0_today"],
        lang_code=lang,
        # Extended context (v2 — accuracy stack)
        soil_moisture_deep=weather.get("soil_moisture_deep", 0.0),
        ndvi_7d_ago=ndvi_data.get("ndvi_7d_ago", ndvi_data["ndvi"]),
        rainfall_30d=weather.get("total_rainfall_30d", 0.0),
        normal_rain_30d=weather.get("avg_daily_rainfall_30d", 3.0) * 30,
        temp_min=weather.get("temp_min", 20.0),
        forecast_rain_7d=sum(weather.get("forecast_rainfall", []) or []),
        confidence=accuracy["confidence"],
        warnings=accuracy["warnings"],
    )
    result["gemini_advisory"]    = gemini.get("advisory", "")
    result["gemini_source"]      = gemini.get("source", "not_configured")
    result["gemini_drought_level"] = gemini.get("drought_level", "")
    result["gemini_drought_action"]= gemini.get("drought_action", "")
    result["gemini_pest_risk"]   = gemini.get("pest_risk", "")
    result["gemini_pest_name"]   = gemini.get("pest_name", "")
    result["gemini_pest_action"] = gemini.get("pest_action", "")
    result["gemini_sowing_ready"]= gemini.get("sowing_ready", False)
    result["gemini_sowing_advice"]= gemini.get("sowing_advice", "")
    result["gemini_model"]       = gemini.get("model", "")

    # Translate requested language if not Hindi
    if lang != "hi":
        result["drought"]["action_translated"] = translate_advisory(
            drought["action"], lang)
        result["pest"]["action_translated"] = translate_advisory(
            pest["action"], lang)

    with _cache_lock:
        _cache[cache_key] = result

    # Return a copy without the internal cache timestamp
    response = dict(result)
    response["drought"] = dict(result["drought"])
    response["pest"] = dict(result["pest"])
    response["sowing"] = dict(result["sowing"])
    response.pop("_cached_at", None)
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Pathway Output Reader
# ─────────────────────────────────────────────────────────────────────────────

def get_pathway_alerts() -> list:
    """Read all alerts written by the Pathway streaming engine."""
    alerts = []
    try:
        with open(ALERTS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    alerts.append(json.loads(line))
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error("Error reading alerts file: %s", e)
    return alerts


def get_latest_pathway_alert(village_name: str = None) -> dict:
    """Get the most recent alert, optionally filtered by village."""
    alerts = get_pathway_alerts()
    if village_name:
        village_alerts = [a for a in alerts
                          if a.get("village_name", "").lower() == village_name.lower()]
        return village_alerts[-1] if village_alerts else {}
    return alerts[-1] if alerts else {}


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/village")
def village_api():
    """
    GET /api/village?name=Nashik&state=Maharashtra&crop=wheat&lang=hi

    Returns full advisory data for the requested village.
    Geocodes the village name, fetches satellite data, runs AI models.
    """
    name = request.args.get("name", "Nashik").strip()
    state = request.args.get("state", "").strip()
    crop = request.args.get("crop", "").strip()
    lang = request.args.get("lang", "hi").strip()

    # Sanitise inputs — prevent injection
    name = name[:100]
    state = state[:100]
    crop = crop[:50].lower()
    lang = lang[:5] if lang in SUPPORTED_LANGUAGES else "hi"

    # Look up village in our index first (faster + avoids geocoding)
    village_data = VILLAGES_BY_NAME.get(name.lower())

    if village_data:
        lat = village_data["lat"]
        lon = village_data["lon"]
        if not crop:
            crop = village_data.get("crop", "wheat")
        if not state:
            state = village_data.get("state", "")
    else:
        # Geocode the village
        geo = geocode_village(name, state)
        if not geo:
            return jsonify({
                "error": f"Village '{name}' not found. Please check spelling.",
                "suggestion": "Try: Nashik, Varanasi, Anantapur, Ludhiana, Guntur"
            }), 404
        lat = geo["lat"]
        lon = geo["lon"]

    if not crop:
        crop = "wheat"   # default

    try:
        data = build_village_advisory(lat, lon, name, crop, lang)
        return jsonify(data)
    except Exception as e:
        logger.exception("Error building advisory for %s", name)
        return jsonify({"error": "Failed to fetch satellite data. Please try again."}), 500


@app.route("/api/villages")
def villages_list():
    """GET /api/villages — returns list of all indexed villages."""
    summary = [
        {
            "village_id": v["village_id"],
            "village_name": v["village_name"],
            "state": v["state"],
            "crop": v["crop"],
            "lat": v["lat"],
            "lon": v["lon"],
        }
        for v in VILLAGES_INDEX
    ]
    return jsonify({"count": len(summary), "villages": summary})


@app.route("/api/stream")
def stream():
    """
    GET /api/stream — Server-Sent Events endpoint.
    Streams Pathway output updates to the frontend in real-time.
    Frontend usage: new EventSource('/api/stream')
    """
    def generate():
        last_count = 0
        while True:
            alerts = get_pathway_alerts()
            if len(alerts) != last_count and alerts:
                last_count = len(alerts)
                latest = alerts[-1]
                yield f"data: {json.dumps(latest)}\n\n"
            else:
                # Send keepalive
                yield f": keepalive {int(time.time())}\n\n"
            time.sleep(5)

    return Response(generate(), mimetype="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no",
                    })


@app.route("/api/demo")
def demo():
    """
    GET /api/demo — pre-loaded demo data for 3 key villages.
    Used for hackathon presentation when API calls aren't possible.
    """
    demo_data = [
        {
            "village": "Nashik",
            "state": "Maharashtra",
            "crop": "grapes",
            "lat": 20.0059, "lon": 73.7897,
            "soil_moisture": 18.2,
            "ndvi": 0.38,
            "rainfall_7d": 2.1,
            "et0": 5.8,
            "temp_max": 36.4,
            "humidity": 48.0,
            "drought": {"level": "HIGH", "score": 62, "color": "orange",
                        "emoji": "🟠",
                        "action": "Irrigate within 24 hours. Soil moisture dangerously low."},
            "pest": {"pest": "Aphid", "risk": "MODERATE", "color": "yellow", "emoji": "🟡",
                     "action": "Spray neem oil solution this week."},
            "sowing": {"decision": "WAIT — NOT READY", "wait_days": 3, "color": "orange",
                       "emoji": "⏳", "action": "Wait 3 days, check soil moisture first."},
            "advisory_hindi": "🌾 KISAN AI — Nashik (Grapes)\n\n💧 पानी: 🟠 HIGH\n24 घंटे में सिंचाई करें।\n\n🐛 कीट: 🟡 Aphid (MODERATE)\nनीम का तेल इस सप्ताह छिड़कें।\n\n🌱 बुआई: ⏳ 3 दिन प्रतीक्षा करें\n📡 ISRO + NASA satellite data",
            "forecast_dates": ["2026-03-08", "2026-03-09", "2026-03-10", "2026-03-11",
                               "2026-03-12", "2026-03-13", "2026-03-14"],
            "forecast_rainfall": [0, 0, 3.2, 8.1, 4.0, 0, 0],
            "forecast_temp_max": [36, 37, 34, 31, 32, 35, 36],
        },
        {
            "village": "Varanasi",
            "state": "Uttar Pradesh",
            "crop": "wheat",
            "lat": 25.3176, "lon": 82.9739,
            "soil_moisture": 31.5,
            "ndvi": 0.61,
            "rainfall_7d": 12.4,
            "et0": 3.9,
            "temp_max": 28.1,
            "humidity": 68.0,
            "drought": {"level": "HEALTHY", "score": 18, "color": "green",
                        "emoji": "🟢",
                        "action": "No irrigation needed. Crop is well-hydrated."},
            "pest": {"pest": "Fungal Blight (early risk)", "risk": "LOW", "color": "lightgreen",
                     "emoji": "🟢",
                     "action": "Monitor leaves. Humidity slightly elevated."},
            "sowing": {"decision": "SOW NOW", "wait_days": 0, "color": "green",
                       "emoji": "🌱", "action": "Sow wheat today. Conditions optimal."},
            "advisory_hindi": "🌾 KISAN AI — Varanasi (Wheat)\n\n💧 पानी: 🟢 HEALTHY\nसिंचाई की जरूरत नहीं। फसल स्वस्थ है।\n\n🐛 कीट: 🟢 कोई खतरा नहीं\nसामान्य निगरानी जारी रखें।\n\n🌱 बुआई: 🌱 आज बुआई करें\n📡 ISRO + NASA satellite data",
            "forecast_dates": ["2026-03-08", "2026-03-09", "2026-03-10", "2026-03-11",
                               "2026-03-12", "2026-03-13", "2026-03-14"],
            "forecast_rainfall": [2, 0, 0, 5.5, 3.0, 1.0, 0],
            "forecast_temp_max": [28, 30, 31, 29, 27, 28, 29],
        },
        {
            "village": "Anantapur",
            "state": "Andhra Pradesh",
            "crop": "groundnut",
            "lat": 14.6819, "lon": 77.6006,
            "soil_moisture": 11.3,
            "ndvi": 0.22,
            "rainfall_7d": 0.3,
            "et0": 6.9,
            "temp_max": 40.2,
            "humidity": 32.0,
            "drought": {"level": "CRITICAL", "score": 88, "color": "red",
                        "emoji": "🔴",
                        "action": "Irrigate today. Crop is severely stressed."},
            "pest": {"pest": "Whitefly", "risk": "MODERATE", "color": "yellow",
                     "emoji": "🟡",
                     "action": "Hot dry conditions. Use yellow sticky traps."},
            "sowing": {"decision": "WAIT — NOT READY", "wait_days": 60, "color": "orange",
                       "emoji": "🚫", "action": "Off-season. Next sowing window: June-July."},
            "advisory_hindi": "🌾 KISAN AI — Anantapur (Groundnut)\n\n💧 पानी: 🔴 CRITICAL\nआज सिंचाई करें। फसल गंभीर तनाव में है।\n\n🐛 कीट: 🟡 Whitefly (MODERATE)\nपीले चिपचिपे ट्रैप उपयोग करें।\n\n🌱 बुआई: 🚫 जून-जुलाई में करें\n📡 ISRO + NASA satellite data",
            "forecast_dates": ["2026-03-08", "2026-03-09", "2026-03-10", "2026-03-11",
                               "2026-03-12", "2026-03-13", "2026-03-14"],
            "forecast_rainfall": [0, 0, 0, 0, 0.5, 0, 0],
            "forecast_temp_max": [40, 41, 42, 41, 39, 40, 41],
        },
    ]
    return jsonify({"demo_villages": demo_data})


@app.route("/api/translate")
def translate_api():
    """
    GET /api/translate?text=Irrigate+today&lang=ta
    Translates advisory text to the requested language.
    """
    text = request.args.get("text", "").strip()[:500]   # limit length
    lang = request.args.get("lang", "hi").strip()[:5]

    if not text:
        return jsonify({"error": "No text provided"}), 400
    if lang not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"Unsupported language: {lang}",
                        "supported": list(SUPPORTED_LANGUAGES.keys())}), 400

    translated = translate_advisory(text, lang)
    return jsonify({"original": text, "translated": translated, "lang": lang})


@app.route("/api/languages")
def languages_api():
    """GET /api/languages — list all supported languages."""
    return jsonify(SUPPORTED_LANGUAGES)


@app.route("/health")
def health():
    """Health check endpoint."""
    pathway_running = os.path.exists(ALERTS_FILE)
    return jsonify({
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "pathway_output_exists": pathway_running,
        "villages_loaded": len(VILLAGES_INDEX),
    })


# ─────────────────────────────────────────────────────────────────────────────
# WhatsApp Alert (Twilio)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/whatsapp", methods=["POST"])
def whatsapp_alert():
    """
    POST /api/whatsapp
    Body: {"to": "+919876543210", "village": "Nashik", "crop": "wheat", "lang": "hi"}

    Sends a WhatsApp advisory via Twilio.
    """
    body = request.get_json(silent=True) or {}
    to_number = body.get("to", "").strip()
    village_name = body.get("village", "Nashik").strip()
    crop = body.get("crop", "wheat").strip()
    lang = body.get("lang", "hi").strip()

    # Input validation
    if not to_number or not to_number.startswith("+"):
        return jsonify({"error": "Invalid phone number. Use E.164 format (+919876543210)"}), 400
    if len(to_number) > 20:
        return jsonify({"error": "Phone number too long"}), 400

    # Get advisory
    village_data = VILLAGES_BY_NAME.get(village_name.lower())
    if village_data:
        lat, lon = village_data["lat"], village_data["lon"]
        if not crop:
            crop = village_data.get("crop", "wheat")
    else:
        geo = geocode_village(village_name)
        if not geo:
            return jsonify({"error": f"Village '{village_name}' not found"}), 404
        lat, lon = geo["lat"], geo["lon"]

    data = build_village_advisory(lat, lon, village_name, crop, lang)
    message_text = data.get("advisory_hindi", "")

    # Send via Twilio
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    if not account_sid or account_sid.startswith("your_"):
        return jsonify({
            "status": "demo_mode",
            "message": "Twilio not configured. Message that would be sent:",
            "preview": message_text,
        })

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=message_text,
            from_=from_number,
            to=f"whatsapp:{to_number}",
        )
        return jsonify({"status": "sent", "sid": message.sid})
    except ImportError:
        return jsonify({"error": "Twilio package not installed"}), 500
    except Exception as e:
        logger.error("Twilio send failed: %s", e)
        return jsonify({"error": "Failed to send WhatsApp message"}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Gemini AI Advisory Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/gemini")
def gemini_api():
    """
    GET /api/gemini?name=Nashik&crop=grapes&lang=hi

    Returns Gemini AI expert advisory for the village in the requested language.
    Requires GEMINI_API_KEY in .env.
    """
    name  = request.args.get("name", "Nashik").strip()[:100]
    crop  = request.args.get("crop", "wheat").strip()[:50].lower()
    lang  = request.args.get("lang", "hi").strip()[:5]

    if lang not in SUPPORTED_LANGUAGES:
        lang = "hi"

    # Resolve coordinates
    village_data = VILLAGES_BY_NAME.get(name.lower())
    if village_data:
        lat  = village_data["lat"]
        lon  = village_data["lon"]
        state = village_data.get("state", "")
        if not crop or crop == "wheat":
            crop = village_data.get("crop", "wheat")
    else:
        geo = geocode_village(name)
        if not geo:
            return jsonify({"error": f"Village '{name}' not found"}), 404
        lat, lon, state = geo["lat"], geo["lon"], ""

    # Fetch satellite data
    try:
        weather  = fetch_all_satellite_data(lat, lon)
        ndvi_data = fetch_ndvi(lat, lon)
    except Exception as e:
        return jsonify({"error": "Failed to fetch satellite data"}), 500

    # Cross-validation
    nasa_data = {k: weather.get(k) for k in
                 ("source", "avg_daily_rainfall_30d", "total_rainfall_30d",
                  "avg_temp_30d", "rainfall_history")}
    accuracy = cross_validate(weather, nasa_data, ndvi_data)

    # Gemini advisory
    gemini = get_gemini_advisory(
        village=name, state=state, crop=crop,
        soil_moisture=weather["soil_moisture"],
        ndvi=ndvi_data["ndvi"],
        rainfall_7d=weather["rainfall_7d"],
        temp_max=weather["temp_max"],
        humidity=weather["humidity"],
        et0=weather["et0_today"],
        lang_code=lang,
        soil_moisture_deep=weather.get("soil_moisture_deep", 0.0),
        ndvi_7d_ago=ndvi_data.get("ndvi_7d_ago", ndvi_data["ndvi"]),
        rainfall_30d=weather.get("total_rainfall_30d", 0.0),
        normal_rain_30d=weather.get("avg_daily_rainfall_30d", 3.0) * 30,
        temp_min=weather.get("temp_min", 20.0),
        forecast_rain_7d=sum(weather.get("forecast_rainfall", []) or []),
        confidence=accuracy["confidence"],
        warnings=accuracy["warnings"],
    )

    return jsonify({
        "village": name,
        "crop": crop,
        "lang": lang,
        "soil_moisture": weather["soil_moisture"],
        "soil_moisture_deep": weather.get("soil_moisture_deep", 0.0),
        "ndvi": ndvi_data["ndvi"],
        "rainfall_7d": weather["rainfall_7d"],
        "temp_max": weather["temp_max"],
        "humidity": weather["humidity"],
        "et0": weather["et0_today"],
        # Structured Gemini output
        "gemini_advisory":      gemini.get("advisory", ""),
        "drought_level":        gemini.get("drought_level", ""),
        "drought_action":       gemini.get("drought_action", ""),
        "pest_risk":            gemini.get("pest_risk", ""),
        "pest_name":            gemini.get("pest_name", ""),
        "pest_action":          gemini.get("pest_action", ""),
        "sowing_ready":         gemini.get("sowing_ready", False),
        "sowing_advice":        gemini.get("sowing_advice", ""),
        "voice_message":        gemini.get("voice_message", ""),
        "confidence_note":      gemini.get("confidence_note", ""),
        # Data quality
        "accuracy_confidence":  accuracy["confidence"],
        "accuracy_warnings":    accuracy["warnings"],
        "gemini_source":        gemini.get("source", "not_configured"),
        "model":                gemini.get("model", ""),
        "timestamp":            weather["timestamp"],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Voice Alert Endpoint (ElevenLabs → Twilio WhatsApp)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/voice", methods=["POST"])
def voice_alert():
    """
    POST /api/voice
    Body: {
        "to": "+916377866035",
        "village": "Nashik",
        "crop": "grapes",
        "lang": "hi",
        "text": "optional — override advisory text"
    }

    Generates ElevenLabs voice MP3 from advisory and sends via Twilio WhatsApp.
    Requires ELEVENLABS_API_KEY, TWILIO_* in .env.
    Optional: PUBLIC_BASE_URL in .env for media hosting (use ngrok for local).
    """
    body = request.get_json(silent=True) or {}
    to_number    = body.get("to", "").strip()
    village_name = body.get("village", "Nashik").strip()[:100]
    crop         = body.get("crop", "wheat").strip()[:50].lower()
    lang         = body.get("lang", "hi").strip()[:5]
    custom_text  = body.get("text", "").strip()[:1000]

    if not to_number or not to_number.startswith("+"):
        return jsonify({"error": "Invalid phone number. Use E.164 format (+919876543210)"}), 400
    if len(to_number) > 20:
        return jsonify({"error": "Phone number too long"}), 400
    if lang not in SUPPORTED_LANGUAGES:
        lang = "hi"

    # Build advisory text if not provided
    if not custom_text:
        village_data = VILLAGES_BY_NAME.get(village_name.lower())
        if village_data:
            lat, lon = village_data["lat"], village_data["lon"]
            if not crop or crop == "wheat":
                crop = village_data.get("crop", "wheat")
        else:
            geo = geocode_village(village_name)
            if not geo:
                return jsonify({"error": f"Village '{village_name}' not found"}), 404
            lat, lon = geo["lat"], geo["lon"]

        try:
            data = build_village_advisory(lat, lon, village_name, crop, lang)
            # Prefer Gemini advisory if available
            custom_text = data.get("gemini_advisory") or data.get("advisory_hindi", "")
        except Exception as e:
            return jsonify({"error": "Failed to build advisory"}), 500

    if not custom_text:
        return jsonify({"error": "No advisory text available"}), 400

    public_base_url = (
        os.getenv("PUBLIC_BASE_URL")
        or os.getenv("RENDER_EXTERNAL_URL")   # Render auto-sets this
        or request.host_url.rstrip("/")
    )
    result = send_whatsapp_voice(
        advisory_text=custom_text,
        to_number=to_number,
        lang_code=lang,
        public_base_url=public_base_url,
    )
    return jsonify(result)


@app.route("/api/voice/preview", methods=["POST"])
def voice_preview():
    """
    POST /api/voice/preview
    Body: {"text": "आज सिंचाई करें।", "lang": "hi"}

    Generates audio and returns the filename — for demo preview in dashboard.
    Does NOT send to Twilio.
    """
    body = request.get_json(silent=True) or {}
    text = body.get("text", "").strip()[:1000]
    lang = body.get("lang", "hi").strip()[:5]

    if not text:
        return jsonify({"error": "No text provided"}), 400

    result = generate_voice_alert(text, lang)
    if result.get("success"):
        filename = result["filename"]
        return jsonify({
            "success": True,
            "audio_url": f"/static/audio/{filename}",
            "chars_used": result.get("chars_used", 0),
            "source": result.get("source"),
        })
    return jsonify({"success": False, "error": result.get("error", "Generation failed")}), 500



# ─────────────────────────────────────────────────────────────────────────────
# Farmer Feedback Loop (Layer 4)
# ─────────────────────────────────────────────────────────────────────────────

FEEDBACK_FILE = os.path.join(os.path.dirname(__file__), "data", "feedback.jsonl")


@app.route("/api/feedback", methods=["POST"])
def feedback_api():
    """
    POST /api/feedback
    Body: {
        "village":    "Nashik",
        "crop":       "grapes",
        "prediction": "drought_HIGH",
        "correct":    true,
        "notes":      "Optional free text from farmer"
    }

    Records farmer feedback to data/feedback.jsonl.
    Returns running accuracy stats per crop/village.

    Privacy: no phone numbers stored — only village + crop + boolean.
    """
    body = request.get_json(silent=True) or {}

    village    = str(body.get("village", "")).strip()[:100]
    crop       = str(body.get("crop", "")).strip()[:50].lower()
    prediction = str(body.get("prediction", "")).strip()[:50]
    correct    = body.get("correct")
    notes      = str(body.get("notes", "")).strip()[:500]

    if not village or correct is None:
        return jsonify({"error": "village and correct are required fields"}), 400

    entry = {
        "ts":         datetime.utcnow().isoformat(),
        "village":    village,
        "crop":       crop,
        "prediction": prediction,
        "correct":    bool(correct),
        "notes":      notes,
    }

    try:
        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error("Feedback write failed: %s", e)
        return jsonify({"error": "Could not save feedback"}), 500

    # Compute running stats
    stats = _compute_feedback_stats(village=village, crop=crop)
    return jsonify({"status": "saved", "stats": stats})


def _compute_feedback_stats(village: str = None, crop: str = None) -> dict:
    """Read feedback.jsonl and compute accuracy per village+crop combo."""
    records = []
    try:
        with open(FEEDBACK_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except FileNotFoundError:
        return {"total": 0, "correct": 0, "accuracy_pct": None}

    # Filter to this village/crop if requested
    subset = records
    if village:
        subset = [r for r in subset if r.get("village", "").lower() == village.lower()]
    if crop:
        subset = [r for r in subset if r.get("crop", "").lower() == crop.lower()]

    total   = len(subset)
    correct = sum(1 for r in subset if r.get("correct"))
    return {
        "total":        total,
        "correct":      correct,
        "accuracy_pct": round(100 * correct / total, 1) if total else None,
        "global_total": len(records),
    }


@app.route("/api/feedback/stats")
def feedback_stats_api():
    """GET /api/feedback/stats?village=Nashik&crop=grapes"""
    village = request.args.get("village", "").strip()[:100]
    crop    = request.args.get("crop", "").strip()[:50].lower()
    stats   = _compute_feedback_stats(village or None, crop or None)
    return jsonify(stats)


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development") == "development"
    logger.info("Starting KISAN AI on http://localhost:%d", port)
    app.run(debug=debug, port=port, host="0.0.0.0")

