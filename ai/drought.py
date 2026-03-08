"""
ai/drought.py
-------------
Drought Risk Model — scores soil moisture, NDVI, rainfall deficit,
and evapotranspiration to produce a 0-100 risk score with action advice.
Uses per-crop thresholds from data/crop_thresholds.json.
"""

import json
import os

_THRESHOLDS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "crop_thresholds.json")
_THRESHOLDS: dict = {}


def _load_thresholds() -> dict:
    global _THRESHOLDS
    if not _THRESHOLDS:
        try:
            with open(_THRESHOLDS_PATH, "r", encoding="utf-8") as f:
                _THRESHOLDS = json.load(f)
        except Exception:
            _THRESHOLDS = {}
    return _THRESHOLDS


def _get_crop_thresholds(crop: str) -> dict:
    thresholds = _load_thresholds()
    crop_key = crop.lower().strip() if crop else "default"
    return thresholds.get(crop_key, thresholds.get("default", {
        "soil_moisture_critical": 20,
        "soil_moisture_moderate": 30,
        "ndvi_healthy": 0.55,
        "ndvi_moderate": 0.35,
        "ndvi_critical": 0.20,
        "rainfall_weekly_min": 8,
        "water_requirement_mm_day": 4.5,
    }))


def drought_risk_model(
    soil_moisture: float,    # percentage (0-100)
    ndvi: float,             # 0-1 (satellite vegetation index)
    rainfall_7d: float,      # mm total last 7 days
    et0: float,              # mm/day evapotranspiration
    crop: str = "wheat",     # crop type for thresholds
    rainfall_deficit: float = 0.0,  # mm vs historical baseline
) -> dict:
    """
    Compute drought risk for a single 1-hour observation.

    Returns:
        dict with keys: score (0-100), level, color, action, details
    """
    t = _get_crop_thresholds(crop)
    score = 0
    drivers = []

    # ── Soil Moisture (40% weight) ────────────────────────────────────────────
    sm_critical = t.get("soil_moisture_critical", 20)
    sm_moderate = t.get("soil_moisture_moderate", 30)

    if soil_moisture < sm_critical:
        score += 40
        drivers.append(f"Soil moisture critically low ({soil_moisture:.1f}%)")
    elif soil_moisture < sm_moderate:
        pts = int(25 * (sm_moderate - soil_moisture) / (sm_moderate - sm_critical))
        score += pts
        drivers.append(f"Soil moisture below optimal ({soil_moisture:.1f}%)")
    elif soil_moisture < sm_moderate + 10:
        score += 8
        drivers.append(f"Soil moisture slightly low ({soil_moisture:.1f}%)")

    # ── NDVI — Crop Greenness (30% weight) ────────────────────────────────────
    ndvi_healthy = t.get("ndvi_healthy", 0.55)
    ndvi_moderate = t.get("ndvi_moderate", 0.35)
    ndvi_critical = t.get("ndvi_critical", 0.20)

    if ndvi < ndvi_critical:
        score += 30
        drivers.append(f"NDVI critically low — sparse vegetation ({ndvi:.2f})")
    elif ndvi < ndvi_moderate:
        pts = int(20 * (ndvi_moderate - ndvi) / (ndvi_moderate - ndvi_critical))
        score += pts
        drivers.append(f"NDVI below healthy range ({ndvi:.2f})")
    elif ndvi < ndvi_healthy:
        score += 8
        drivers.append(f"Vegetation moderately stressed ({ndvi:.2f})")

    # ── Rainfall Deficit (20% weight) ─────────────────────────────────────────
    weekly_min = t.get("rainfall_weekly_min", 8)
    if rainfall_7d < weekly_min * 0.25:   # < 25% of minimum
        score += 20
        drivers.append(f"Severe rainfall deficit (only {rainfall_7d:.1f}mm in 7 days)")
    elif rainfall_7d < weekly_min * 0.6:
        pts = int(12 * (weekly_min * 0.6 - rainfall_7d) / (weekly_min * 0.6))
        score += pts
        drivers.append(f"Low rainfall ({rainfall_7d:.1f}mm vs {weekly_min:.0f}mm expected)")

    # Historical deficit bonus
    if rainfall_deficit > 20:
        score += 5
        drivers.append(f"Historical rainfall deficit ({rainfall_deficit:.0f}mm below normal)")

    # ── Evapotranspiration Stress (10% weight) ────────────────────────────────
    water_req = t.get("water_requirement_mm_day", 4.5)
    if et0 > water_req * 1.5:
        score += 10
        drivers.append(f"High evapotranspiration ({et0:.1f}mm/day)")
    elif et0 > water_req * 1.2:
        score += 5
        drivers.append(f"Elevated evapotranspiration ({et0:.1f}mm/day)")

    score = min(score, 100)

    # ── Risk Classification ───────────────────────────────────────────────────
    if score >= 70:
        return {
            "score": score,
            "level": "CRITICAL",
            "color": "red",
            "emoji": "🔴",
            "action": "Irrigate today — crop is under severe water stress. "
                      "Every hour of delay increases yield loss.",
            "action_hindi": "आज सिंचाई करें। फसल गंभीर जल तनाव में है।",
            "days_until_damage": 0,
            "drivers": drivers,
        }
    elif score >= 50:
        return {
            "score": score,
            "level": "HIGH",
            "color": "orange",
            "emoji": "🟠",
            "action": "Irrigate within 24 hours. Soil moisture is dangerously low. "
                      "Check water pump and channels today.",
            "action_hindi": "24 घंटे में सिंचाई करें। मिट्टी की नमी खतरनाक स्तर पर है।",
            "days_until_damage": 1,
            "drivers": drivers,
        }
    elif score >= 35:
        return {
            "score": score,
            "level": "MODERATE",
            "color": "yellow",
            "emoji": "🟡",
            "action": "Plan irrigation within 2–3 days. Monitor soil cracks. "
                      "Avoid leaf burn by irrigating in early morning or evening.",
            "action_hindi": "2-3 दिन में सिंचाई की योजना बनाएं। फसल की निगरानी करें।",
            "days_until_damage": 3,
            "drivers": drivers,
        }
    else:
        return {
            "score": score,
            "level": "HEALTHY",
            "color": "green",
            "emoji": "🟢",
            "action": "No irrigation needed. Crop is well-hydrated. "
                      "Next check in 2 days.",
            "action_hindi": "सिंचाई की जरूरत नहीं। फसल स्वस्थ है।",
            "days_until_damage": 7,
            "drivers": drivers,
        }
