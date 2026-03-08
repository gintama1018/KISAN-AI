"""
pipeline/stream.py
------------------
KISAN AI — Pathway Real-Time Streaming Engine

This is the core of the system. It:
  1. Loads the village list from data/villages.jsonl
  2. Polls Open-Meteo every hour for each village (or batch of villages)
  3. Fetches NDVI from AgroMonitoring
  4. Runs drought + pest models as Pathway UDFs
  5. Writes results to /tmp/kisan_alerts.jsonl (Flask reads this live)

Run this in a separate terminal:
    python pipeline/stream.py

The Flask app reads /tmp/kisan_alerts.jsonl and serves SSE to the frontend.
"""

import os
import sys
import json
import time
import logging

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pathway as pw
from pathway.io.python import ConnectorSubject

from data.satellite import fetch_all_satellite_data
from data.ndvi import fetch_ndvi
from ai.drought import drought_risk_model
from ai.pest import pest_risk_model
from ai.sowing import sowing_window_model
from ai.translate import build_full_advisory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

VILLAGES_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "villages.jsonl")
ALERTS_FILE = os.getenv("ALERTS_FILE", "/tmp/kisan_alerts.jsonl")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "3600"))   # 1 hour default


# ─────────────────────────────────────────────────────────────────────────────
# Schema Definition
# ─────────────────────────────────────────────────────────────────────────────

class KisanAlertSchema(pw.Schema):
    village_id:       str
    village_name:     str
    state:            str
    crop:             str
    lat:              float
    lon:              float
    timestamp:        str
    soil_moisture:    float
    ndvi:             float
    rainfall_7d:      float
    et0:              float
    temp_max:         float
    humidity:         float
    drought_score:    int
    drought_level:    str
    drought_action:   str
    pest_name:        str
    pest_risk:        str
    pest_action:      str
    sowing_decision:  str
    sowing_wait_days: int
    advisory_hindi:   str
    source:           str


# ─────────────────────────────────────────────────────────────────────────────
# Village Loader
# ─────────────────────────────────────────────────────────────────────────────

def load_villages() -> list:
    villages = []
    try:
        with open(VILLAGES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    villages.append(json.loads(line))
        logger.info("Loaded %d villages", len(villages))
    except Exception as e:
        logger.error("Failed to load villages file: %s", e)
    return villages


# ─────────────────────────────────────────────────────────────────────────────
# Core Processing — per village
# ─────────────────────────────────────────────────────────────────────────────

def process_village(village: dict) -> dict:
    """
    Fetch all data and run AI models for a single village.
    Returns a flat dict matching KisanAlertSchema.
    """
    lat = village["lat"]
    lon = village["lon"]
    crop = village.get("crop", "wheat")
    village_name = village.get("village_name", "Unknown")

    logger.info("Processing %s (%.4f, %.4f) — %s", village_name, lat, lon, crop)

    # 1. Fetch satellite data
    weather = fetch_all_satellite_data(lat, lon)

    # 2. Fetch NDVI
    ndvi_data = fetch_ndvi(lat, lon)

    # 3. Run AI models
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

    # 4. Build Hindi advisory
    advisory_hindi = build_full_advisory(
        drought=drought, pest=pest, sowing=sowing,
        lang_code="hi",
        village_name=village_name,
        crop=crop,
    )

    return {
        "village_id":      village["village_id"],
        "village_name":    village_name,
        "state":           village.get("state", ""),
        "crop":            crop,
        "lat":             lat,
        "lon":             lon,
        "timestamp":       weather["timestamp"],
        "soil_moisture":   weather["soil_moisture"],
        "ndvi":            ndvi_data["ndvi"],
        "rainfall_7d":     weather["rainfall_7d"],
        "et0":             weather["et0_today"],
        "temp_max":        weather["temp_max"],
        "humidity":        weather["humidity"],
        # Drought
        "drought_score":   drought["score"],
        "drought_level":   drought["level"],
        "drought_action":  drought["action"],
        "drought_color":   drought["color"],
        # Pest
        "pest_name":       pest["pest"],
        "pest_risk":       pest["risk"],
        "pest_action":     pest["action"],
        "pest_color":      pest["color"],
        # Sowing
        "sowing_decision": sowing["decision"],
        "sowing_wait_days": sowing["wait_days"],
        "sowing_action":   sowing["action"],
        "sowing_color":    sowing["color"],
        # Advisory
        "advisory_hindi":  advisory_hindi,
        "source":          weather.get("source", "open-meteo"),
        # Full data for frontend charts
        "forecast_rainfall": weather.get("forecast_rainfall", []),
        "forecast_temp_max": weather.get("forecast_temp_max", []),
        "forecast_dates":    weather.get("forecast_dates", []),
        "ndvi_trend":        ndvi_data.get("ndvi_trend", "stable"),
        "ndvi_7d_ago":       ndvi_data.get("ndvi_7d_ago", ndvi_data["ndvi"]),
        "rainfall_today":    weather.get("rainfall_today", 0),
        "current_temp":      weather.get("current_temp", weather["temp_max"]),
        "soil_temp":         weather.get("soil_temp", 22.0),
        "wind_speed":        weather.get("wind_speed", 10.0),
        "drought_drivers":   drought.get("drivers", []),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Pathway Connector — polls all villages on a schedule
# ─────────────────────────────────────────────────────────────────────────────

class VillagePollingConnector(ConnectorSubject):
    """
    Pathway ConnectorSubject that polls satellite APIs for every village
    at a configurable interval and pushes updates into the Pathway stream.
    """

    def __init__(self, villages: list, poll_interval: int = 3600):
        super().__init__()
        self.villages = villages
        self.poll_interval = poll_interval

    def run(self):
        while True:
            logger.info("Starting polling cycle for %d villages", len(self.villages))
            for village in self.villages:
                try:
                    alert = process_village(village)
                    self.next(**{k: v for k, v in alert.items()
                                 if k in KisanAlertSchema.__annotations__})
                except Exception as e:
                    logger.error("Failed to process village %s: %s",
                                 village.get("village_name"), e)
                # Small delay between villages to avoid rate limiting
                time.sleep(2)

            logger.info("Polling cycle complete. Next in %ds", self.poll_interval)
            time.sleep(self.poll_interval)


# ─────────────────────────────────────────────────────────────────────────────
# Pathway UDF Wrappers
# ─────────────────────────────────────────────────────────────────────────────

@pw.udf
def udf_drought(soil_moisture: float, ndvi: float,
                rainfall_7d: float, et0: float) -> str:
    result = drought_risk_model(soil_moisture, ndvi, rainfall_7d, et0)
    return json.dumps(result)


@pw.udf
def udf_pest(temp_max: float, humidity: float,
             ndvi: float, ndvi_prev: float) -> str:
    result = pest_risk_model(temp_max, 20.0, humidity, ndvi, ndvi_prev)
    return json.dumps(result)


# ─────────────────────────────────────────────────────────────────────────────
# Pathway Table Transforms (optional — enrich the stream)
# ─────────────────────────────────────────────────────────────────────────────

def build_pathway_pipeline(villages: list, poll_interval: int = 3600):
    """
    Build and return the Pathway streaming pipeline.
    """
    # Read from our custom polling connector
    table = pw.io.python.read(
        VillagePollingConnector(villages, poll_interval),
        schema=KisanAlertSchema,
    )

    # Optionally enrich the stream with re-scored drought (UDF example)
    enriched = table.select(
        pw.this.village_id,
        pw.this.village_name,
        pw.this.state,
        pw.this.crop,
        pw.this.lat,
        pw.this.lon,
        pw.this.timestamp,
        pw.this.soil_moisture,
        pw.this.ndvi,
        pw.this.rainfall_7d,
        pw.this.et0,
        pw.this.temp_max,
        pw.this.humidity,
        pw.this.drought_score,
        pw.this.drought_level,
        pw.this.drought_action,
        pw.this.pest_name,
        pw.this.pest_risk,
        pw.this.pest_action,
        pw.this.sowing_decision,
        pw.this.sowing_wait_days,
        pw.this.advisory_hindi,
        pw.this.source,
    )

    # Write output — Flask reads this file
    os.makedirs(os.path.dirname(ALERTS_FILE), exist_ok=True)
    pw.io.jsonlines.write(enriched, ALERTS_FILE)

    return enriched


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("=== KISAN AI PATHWAY STREAM ENGINE STARTING ===")
    logger.info("Output file: %s", ALERTS_FILE)
    logger.info("Poll interval: %ds", POLL_INTERVAL_SECONDS)

    villages = load_villages()
    if not villages:
        logger.error("No villages loaded — check data/villages.jsonl")
        sys.exit(1)

    # For demo: limit to first 10 villages to avoid API rate limits
    demo_villages = villages[:10]
    logger.info("Running with %d villages (demo mode)", len(demo_villages))

    pipeline = build_pathway_pipeline(demo_villages, POLL_INTERVAL_SECONDS)
    pw.run(monitoring_level=pw.MonitoringLevel.NONE)
