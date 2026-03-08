"""
ai/sowing.py
------------
Sowing Window Model — determines whether current conditions are suitable
for sowing, and if not, estimates how many days to wait.

Considers:
  - Soil temperature (germination requirement)
  - 7-day rainfall forecast (adequate moisture for germination)
  - ET₀ (evapotranspiration — water loss risks)
  - Season calendar (crop-specific sowing months)
"""

import json
import os
from datetime import datetime
from typing import Optional

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


def _get_crop(crop: str) -> dict:
    thresholds = _load_thresholds()
    crop_key = crop.lower().strip() if crop else "default"
    return thresholds.get(crop_key, thresholds.get("default", {}))


def sowing_window_model(
    soil_temp: float,            # °C at 5cm depth
    forecast_rainfall: list,     # mm per day, 7-day list
    et0: float,                  # mm/day evapotranspiration
    soil_moisture: float,        # current soil moisture %
    crop: str = "wheat",
    current_rainfall: float = 0.0,  # mm today
) -> dict:
    """
    Assess sowing conditions and return a recommendation.

    Returns:
        dict with decision, wait_days, reason, and advisory text
    """
    t = _get_crop(crop)
    if not t:
        t = {"temp_min_sowing": 18, "temp_max_sowing": 32,
             "temp_germination": 24, "rainfall_weekly_min": 8,
             "soil_moisture_critical": 20, "sowing_months": [6, 7]}

    month = datetime.utcnow().month
    sowing_months = t.get("sowing_months", [6, 7])
    temp_min = t.get("temp_min_sowing", 15)
    temp_max = t.get("temp_max_sowing", 35)
    temp_germ = t.get("temp_germination", 24)
    sm_critical = t.get("soil_moisture_critical", 20)
    weekly_rain_min = t.get("rainfall_weekly_min", 8)

    issues = []
    wait_days = 0

    # ── 1. Season Check ───────────────────────────────────────────────────────
    in_sowing_season = month in sowing_months
    months_ahead = 0
    if not in_sowing_season:
        # Calculate months until next sowing window
        for i in range(1, 13):
            if (month + i - 1) % 12 + 1 in sowing_months:
                months_ahead = i
                break
        issues.append(
            f"Off-season: optimal sowing window is "
            f"{_months_to_names(sowing_months)}. "
            f"Wait {months_ahead} month(s)."
        )
        wait_days = max(wait_days, months_ahead * 30)

    # ── 2. Soil Temperature Check ─────────────────────────────────────────────
    if soil_temp < temp_min:
        days_cold = int((temp_min - soil_temp) * 3)   # rough estimate
        wait_days = max(wait_days, days_cold)
        issues.append(
            f"Soil too cold ({soil_temp:.1f}°C). "
            f"Germination needs >{temp_min}°C. "
            f"Wait ~{days_cold} days."
        )
    elif soil_temp > temp_max + 5:
        issues.append(
            f"Soil too hot ({soil_temp:.1f}°C). "
            f"Consider sowing after 5pm or wait for a cooler spell."
        )
        wait_days = max(wait_days, 3)

    # ── 3. Soil Moisture Check ────────────────────────────────────────────────
    if soil_moisture < sm_critical:
        issues.append(
            f"Soil too dry ({soil_moisture:.1f}%). "
            f"Pre-sow irrigation needed — bring soil to field capacity before sowing."
        )
        wait_days = max(wait_days, 1)

    # ── 4. Rainfall Forecast Check ────────────────────────────────────────────
    rain_7d_forecast = sum(forecast_rainfall[:7]) if forecast_rainfall else 0
    rain_3d_forecast = sum(forecast_rainfall[:3]) if forecast_rainfall else 0

    if rain_7d_forecast < weekly_rain_min * 0.5:
        if soil_moisture < sm_critical + 10:
            issues.append(
                f"Low rain forecast ({rain_7d_forecast:.0f}mm in 7 days). "
                f"Irrigation will be critical post-sowing."
            )
            wait_days = max(wait_days, 0)   # can sow but warning

    # ── 5. ET₀ — Water Demand Risk ────────────────────────────────────────────
    water_req = t.get("water_requirement_mm_day", 4.5)
    if et0 > water_req * 1.6:
        issues.append(
            f"High evapotranspiration ({et0:.1f}mm/day). "
            f"Pre-germination moisture loss risk is elevated."
        )
        wait_days = max(wait_days, 1)

    # ── Decision ──────────────────────────────────────────────────────────────
    optimal_soil = sm_critical + 10
    ideal_temp = temp_min <= soil_temp <= temp_germ + 5
    good_rain_coming = rain_3d_forecast > weekly_rain_min * 0.4

    if not issues and ideal_temp and soil_moisture >= optimal_soil:
        return {
            "decision": "SOW NOW",
            "color": "green",
            "emoji": "🌱",
            "wait_days": 0,
            "confidence": 0.90,
            "reason": f"Ideal sowing conditions: soil temp {soil_temp:.1f}°C, "
                      f"moisture {soil_moisture:.1f}%, good forecast.",
            "action": f"Sow {crop} today. Conditions are optimal. "
                      "Soil is moist and temperature is in germination range.",
            "action_hindi": f"आज {crop} की बुआई करें। स्थिति बेहतरीन है।",
        }
    elif wait_days <= 2 and in_sowing_season and not issues:
        return {
            "decision": "SOW SOON",
            "color": "lightgreen",
            "emoji": "🌿",
            "wait_days": 1,
            "confidence": 0.75,
            "reason": "Conditions nearly ready. Minor improvements expected.",
            "action": f"Wait 1–2 days before sowing {crop}. "
                      "Run irrigation today to bring moisture to optimal level.",
            "action_hindi": f"1-2 दिन में {crop} की बुआई करें। आज सिंचाई करें।",
        }
    elif 0 < wait_days <= 7:
        issue_str = "; ".join(issues[:2]) if issues else "Conditions suboptimal"
        return {
            "decision": f"WAIT {wait_days} DAYS",
            "color": "yellow",
            "emoji": "⏳",
            "wait_days": wait_days,
            "confidence": 0.70,
            "reason": issue_str,
            "action": f"Do not sow {crop} yet. Wait {wait_days} days. "
                      "Prepare fields and check irrigation channels.",
            "action_hindi": f"{wait_days} दिन बाद बुआई करें। अभी खेत तैयार करें।",
        }
    else:
        issue_str = "; ".join(issues[:2]) if issues else "Conditions not suitable"
        return {
            "decision": "WAIT — NOT READY",
            "color": "orange",
            "emoji": "🚫",
            "wait_days": wait_days,
            "confidence": 0.80,
            "reason": issue_str,
            "action": f"Sowing {crop} now is not recommended. "
                      f"Wait at least {wait_days} days. "
                      "Use this time for field preparation.",
            "action_hindi": f"अभी बुआई न करें। {wait_days} दिन प्रतीक्षा करें।",
        }


def _months_to_names(month_nums: list) -> str:
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return ", ".join(names[m - 1] for m in month_nums if 1 <= m <= 12)
