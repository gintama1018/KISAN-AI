"""
data/ndvi.py
------------
Fetches real NDVI (Normalized Difference Vegetation Index) data from:
  • AgroMonitoring API — free tier, 60 calls/day
  • Open-Meteo NDVI estimation fallback (derived from soil moisture + temp)
"""

import os
import math
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

AGRO_BASE = "https://agromonitoring.com/api/image/search"
AGRO_POLYGON_URL = "https://agromonitoring.com/api/agromonitoring/v1.1/polygons"


def _build_farm_polygon(lat: float, lon: float, radius_deg: float = 0.01) -> dict:
    """
    Build a square polygon around the given lat/lon as a GeoJSON feature.
    Default radius ≈ 1km for a typical smallholder farm.
    """
    return {
        "name": f"farm_{lat:.4f}_{lon:.4f}",
        "geo_json": {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [lon - radius_deg, lat - radius_deg],
                    [lon + radius_deg, lat - radius_deg],
                    [lon + radius_deg, lat + radius_deg],
                    [lon - radius_deg, lat + radius_deg],
                    [lon - radius_deg, lat - radius_deg],
                ]]
            }
        }
    }


def fetch_ndvi_agromonitoring(lat: float, lon: float, api_key: str) -> dict:
    """
    Fetch latest NDVI from AgroMonitoring using Sentinel-2 / Landsat-8 imagery.
    Steps:
      1. Create a temporary polygon around the farm
      2. Query the latest NDVI image
    Returns dict with current ndvi, ndvi_7d_ago, and source metadata.
    """
    if not api_key or api_key.startswith("your_"):
        logger.warning("AgroMonitoring key not set — using estimated NDVI")
        return _estimate_ndvi_fallback(lat, lon)

    headers = {"Content-Type": "application/json"}
    polygon_payload = _build_farm_polygon(lat, lon)

    try:
        # --- Step 1: Create polygon ---
        r = requests.post(
            f"{AGRO_POLYGON_URL}?appid={api_key}",
            json=polygon_payload,
            headers=headers,
            timeout=10
        )
        r.raise_for_status()
        polygon_id = r.json().get("id")

        if not polygon_id:
            return _estimate_ndvi_fallback(lat, lon)

        # --- Step 2: Query NDVI imagery ---
        now = int(datetime.utcnow().timestamp())
        week_ago = int((datetime.utcnow() - timedelta(days=8)).timestamp())

        ndvi_url = f"https://agromonitoring.com/api/image/search?appid={api_key}"
        params = {
            "polyid": polygon_id,
            "datestart": week_ago,
            "dateend": now,
        }
        r2 = requests.get(ndvi_url, params=params, timeout=15)
        r2.raise_for_status()
        images = r2.json()

        if not images:
            return _estimate_ndvi_fallback(lat, lon)

        # Sort by date descending, get latest 2 for delta calculation
        images_sorted = sorted(images, key=lambda x: x.get("dt", 0), reverse=True)
        latest = images_sorted[0]
        prev = images_sorted[1] if len(images_sorted) > 1 else None

        ndvi_current = _extract_ndvi_stats(latest)
        ndvi_prev = _extract_ndvi_stats(prev) if prev else ndvi_current

        # Clean up — delete temporary polygon to stay within free tier
        requests.delete(
            f"{AGRO_POLYGON_URL}/{polygon_id}?appid={api_key}",
            timeout=5
        )

        return {
            "ndvi": round(ndvi_current, 3),
            "ndvi_7d_ago": round(ndvi_prev, 3),
            "ndvi_trend": "improving" if ndvi_current > ndvi_prev else "declining",
            "ndvi_drop_7d": round(ndvi_prev - ndvi_current, 3),
            "source": "agromonitoring-sentinel2",
            "last_image_date": datetime.utcfromtimestamp(
                latest.get("dt", 0)
            ).strftime("%Y-%m-%d") if latest.get("dt") else "unknown",
        }

    except requests.HTTPError as e:
        logger.error("AgroMonitoring HTTP error: %s", e)
        return _estimate_ndvi_fallback(lat, lon)
    except Exception as e:
        logger.error("AgroMonitoring fetch failed: %s", e)
        return _estimate_ndvi_fallback(lat, lon)


def _extract_ndvi_stats(image_record: dict) -> float:
    """Extract mean NDVI from an AgroMonitoring image record."""
    if not image_record:
        return 0.5
    stats = image_record.get("stats", {})
    return stats.get("mean", image_record.get("ndvi", 0.5))


def _estimate_ndvi_fallback(lat: float, lon: float) -> dict:
    """
    Estimate NDVI based on latitude, season, and a sine model.
    Used when AgroMonitoring key is unavailable.
    This is a placeholder — real NDVI requires satellite imagery.
    """
    doy = datetime.utcnow().timetuple().tm_yday   # Day of year 1–365
    # India Kharif season (June–Oct) has higher NDVI; Rabi (Nov–Mar) lower
    # Simple sinusoidal seasonal model: peak NDVI around day 240 (late Aug)
    seasonal_ndvi = 0.35 + 0.25 * math.sin(math.radians((doy - 80) * (360 / 365)))
    # Add slight latitude adjustment (tropical areas greener)
    lat_factor = max(0, (25 - abs(lat - 20)) / 25) * 0.1
    ndvi = round(min(0.9, max(0.1, seasonal_ndvi + lat_factor)), 3)
    ndvi_prev = round(ndvi + 0.02, 3)   # slight improvement over previous week

    return {
        "ndvi": ndvi,
        "ndvi_7d_ago": ndvi_prev,
        "ndvi_trend": "stable",
        "ndvi_drop_7d": round(ndvi_prev - ndvi, 3),
        "source": "estimated-seasonal-model",
        "last_image_date": "estimated",
    }


def fetch_ndvi(lat: float, lon: float) -> dict:
    """
    Public interface: fetch NDVI using AgroMonitoring if key is set,
    otherwise fall back to seasonal estimation.
    """
    api_key = os.getenv("AGRO_API_KEY", "")
    return fetch_ndvi_agromonitoring(lat, lon, api_key)
