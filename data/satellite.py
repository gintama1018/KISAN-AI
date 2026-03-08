"""
data/satellite.py
-----------------
Fetches real satellite-derived data from:
  • Open-Meteo   — soil moisture, ET, rainfall, temperature (NO KEY)
  • NASA POWER   — historical daily data, solar radiation  (NO KEY)
  • Nominatim    — village name → lat/lon                  (NO KEY)
"""

import requests
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Geocoding — Village name → lat/lon
# ─────────────────────────────────────────────────────────────────────────────

def geocode_village(village_name: str, state: str = "") -> Optional[dict]:
    """
    Convert a village/city name to lat/lon using Nominatim (OpenStreetMap).
    Returns {"lat": float, "lon": float, "display_name": str} or None.
    """
    query = f"{village_name}, {state}, India" if state else f"{village_name}, India"
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "in"
    }
    headers = {"User-Agent": "KisanAI/1.0 (agricultural advisory platform)"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data:
            return {
                "lat": float(data[0]["lat"]),
                "lon": float(data[0]["lon"]),
                "display_name": data[0].get("display_name", village_name)
            }
    except Exception as e:
        logger.error("Geocoding failed for %s: %s", village_name, e)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Open-Meteo — Current + 7-day forecast + hourly soil moisture
# ─────────────────────────────────────────────────────────────────────────────

def fetch_openmeteo(lat: float, lon: float) -> dict:
    """
    Fetch current and 7-day forecast from Open-Meteo.
    Returns structured dict with soil moisture, ET, rainfall, temperature.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "precipitation_sum",
            "et0_fao_evapotranspiration",
            "temperature_2m_max",
            "temperature_2m_min",
            "relative_humidity_2m_max",
            "relative_humidity_2m_min",
            "weathercode",
        ],
        "hourly": [
            "soil_moisture_9_to_27cm",    # root zone — agronomically meaningful
            "soil_moisture_27_to_81cm",   # deep root zone
            "soil_temperature_6cm",       # root zone temperature
        ],
        "current_weather": True,
        "timezone": "Asia/Kolkata",
        "forecast_days": 7,
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        raw = r.json()

        daily = raw.get("daily", {})
        hourly = raw.get("hourly", {})
        current = raw.get("current_weather", {})

        # Root-zone soil moisture (9–27 cm) — what crop roots actually feel
        sm_values = hourly.get("soil_moisture_9_to_27cm", [])
        soil_moisture = next((v for v in reversed(sm_values) if v is not None), 25.0)
        # Open-Meteo returns m³/m³ (0–1); convert to % (× 100)
        if soil_moisture < 1.0:
            soil_moisture = round(soil_moisture * 100, 1)

        # Deep root-zone soil moisture (27–81 cm) — sub-soil water reserve
        sm_deep_values = hourly.get("soil_moisture_27_to_81cm", [])
        soil_moisture_deep = next((v for v in reversed(sm_deep_values) if v is not None), 28.0)
        if soil_moisture_deep < 1.0:
            soil_moisture_deep = round(soil_moisture_deep * 100, 1)

        # Root-zone soil temperature (6 cm)
        st_values = hourly.get("soil_temperature_6cm", [])
        soil_temp = next((v for v in reversed(st_values) if v is not None), 22.0)

        # 7-day totals
        rainfall_7d = sum(v for v in (daily.get("precipitation_sum") or []) if v)
        et0_7d = sum(v for v in (daily.get("et0_fao_evapotranspiration") or []) if v)

        # Today's values (index 0)
        precip_list = daily.get("precipitation_sum") or [0]
        et0_list = daily.get("et0_fao_evapotranspiration") or [4]
        temp_max_list = daily.get("temperature_2m_max") or [30]
        temp_min_list = daily.get("temperature_2m_min") or [20]
        humidity_max_list = daily.get("relative_humidity_2m_max") or [60]

        return {
            "source": "open-meteo",
            "lat": lat,
            "lon": lon,
            "timestamp": datetime.utcnow().isoformat(),
            # Current
            "soil_moisture": soil_moisture,
            "soil_moisture_deep": soil_moisture_deep,
            "soil_temp": soil_temp,
            "temp_max": temp_max_list[0] if temp_max_list else 30.0,
            "temp_min": temp_min_list[0] if temp_min_list else 20.0,
            "humidity": humidity_max_list[0] if humidity_max_list else 60.0,
            "current_temp": current.get("temperature", 28.0),
            "wind_speed": current.get("windspeed", 10.0),
            # Aggregates
            "rainfall_today": precip_list[0] if precip_list else 0.0,
            "et0_today": et0_list[0] if et0_list else 4.0,
            "rainfall_7d": round(rainfall_7d, 1),
            "et0_7d": round(et0_7d, 1),
            # Forecast arrays (7 days)
            "forecast_rainfall": daily.get("precipitation_sum", []),
            "forecast_temp_max": daily.get("temperature_2m_max", []),
            "forecast_et0": daily.get("et0_fao_evapotranspiration", []),
            "forecast_dates": daily.get("time", []),
            "forecast_humidity": daily.get("relative_humidity_2m_max", []),
            "hourly_soil_moisture": sm_values[-24:] if sm_values else [],
        }

    except Exception as e:
        logger.error("Open-Meteo fetch failed for %.4f, %.4f: %s", lat, lon, e)
        return _fallback_weather(lat, lon)


def _fallback_weather(lat: float, lon: float) -> dict:
    """Return safe default values if API call fails."""
    return {
        "source": "fallback",
        "lat": lat, "lon": lon,
        "timestamp": datetime.utcnow().isoformat(),
        "soil_moisture": 25.0, "soil_moisture_deep": 28.0, "soil_temp": 22.0,
        "temp_max": 32.0, "temp_min": 20.0, "humidity": 60.0,
        "current_temp": 28.0, "wind_speed": 10.0,
        "rainfall_today": 0.0, "et0_today": 4.5,
        "rainfall_7d": 8.0, "et0_7d": 28.0,
        "forecast_rainfall": [0, 0, 2, 5, 3, 0, 0],
        "forecast_temp_max": [33, 34, 31, 30, 32, 33, 34],
        "forecast_et0": [4.5, 4.8, 4.2, 4.0, 4.3, 4.6, 4.7],
        "forecast_dates": [],
        "forecast_humidity": [55, 58, 65, 72, 68, 60, 57],
        "hourly_soil_moisture": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# NASA POWER API — Historical 30-day baseline
# ─────────────────────────────────────────────────────────────────────────────

def fetch_nasa_power(lat: float, lon: float, days_back: int = 30) -> dict:
    """
    Fetch historical data from NASA POWER API (no key required).
    Used for building drought baselines and historical comparison.
    """
    end_date = datetime.utcnow() - timedelta(days=2)   # POWER has ~2-day lag
    start_date = end_date - timedelta(days=days_back)

    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "PRECTOTCORR,T2M,RH2M,ALLSKY_SFC_SW_DWN,WS2M",
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "format": "JSON"
    }

    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        raw = r.json()

        props = raw.get("properties", {}).get("parameter", {})
        rainfall_hist = list(props.get("PRECTOTCORR", {}).values())
        temp_hist = list(props.get("T2M", {}).values())
        humidity_hist = list(props.get("RH2M", {}).values())
        solar_hist = list(props.get("ALLSKY_SFC_SW_DWN", {}).values())

        # Filter out fill values (-999)
        def clean(lst): return [v for v in lst if v and v > -900]

        rainfall_clean = clean(rainfall_hist)
        avg_rainfall = round(sum(rainfall_clean) / len(rainfall_clean), 2) if rainfall_clean else 3.0
        total_30d = round(sum(rainfall_clean), 1) if rainfall_clean else 90.0

        temp_clean = clean(temp_hist)
        avg_temp = round(sum(temp_clean) / len(temp_clean), 1) if temp_clean else 28.0

        return {
            "source": "nasa-power",
            "avg_daily_rainfall_30d": avg_rainfall,
            "total_rainfall_30d": total_30d,
            "avg_temp_30d": avg_temp,
            "rainfall_history": rainfall_clean,
            "solar_radiation": clean(solar_hist)[-1] if solar_hist else 18.0,
        }

    except Exception as e:
        logger.error("NASA POWER fetch failed: %s", e)
        return {
            "source": "nasa-power-fallback",
            "avg_daily_rainfall_30d": 3.2,
            "total_rainfall_30d": 96.0,
            "avg_temp_30d": 28.5,
            "rainfall_history": [],
            "solar_radiation": 18.0,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Combined fetch — single call to get everything
# ─────────────────────────────────────────────────────────────────────────────

def fetch_all_satellite_data(lat: float, lon: float) -> dict:
    """
    Fetch Open-Meteo (current) + NASA POWER (historical).
    Returns merged dict for AI models.
    """
    weather = fetch_openmeteo(lat, lon)
    history = fetch_nasa_power(lat, lon, days_back=14)

    # Historical deficit: compare current 7d rainfall vs 30d average
    avg_7d_expected = history["avg_daily_rainfall_30d"] * 7
    rainfall_deficit = max(0, avg_7d_expected - weather["rainfall_7d"])

    return {
        **weather,
        **history,
        "rainfall_deficit_7d": round(rainfall_deficit, 1),
    }
