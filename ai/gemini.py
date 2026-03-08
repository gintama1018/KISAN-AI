"""
ai/gemini.py
------------
KISAN AI — Gemini AI Advisory Engine

Replaces rule-based models with Gemini 2.0 Flash (free tier):
  - 15 requests/minute, 1M tokens/day — free at aistudio.google.com
  - Understands crop type, season, region, historical context
  - Generates expert agronomist-level advice, not just risk scores
  - Falls back to rule-based models if Gemini key not set

Usage:
    from ai.gemini import get_gemini_advisory
    result = get_gemini_advisory(
        village="Nashik", state="Maharashtra", crop="grapes",
        soil_moisture=8.3, ndvi=0.31, rainfall_7d=0.0,
        temp_max=37.3, humidity=42.0, et0=6.1,
        lang_code="hi"
    )
"""

import os
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Month → season mapping for Indian agriculture
_SEASON_MAP = {
    1: "Rabi (winter crop)", 2: "Rabi (winter crop)", 3: "Rabi harvest season",
    4: "Pre-Kharif (hot, dry)", 5: "Pre-Kharif (hot, dry)",
    6: "Kharif sowing (monsoon starts)", 7: "Kharif (monsoon peak)",
    8: "Kharif (monsoon peak)", 9: "Kharif (monsoon end)",
    10: "Rabi sowing season", 11: "Rabi sowing season",
    12: "Rabi (early winter)",
}


def _build_prompt(
    village: str, state: str, crop: str,
    soil_moisture: float, ndvi: float,
    rainfall_7d: float, temp_max: float, humidity: float,
    et0: float, lang_code: str,
) -> str:
    season = _SEASON_MAP.get(datetime.now().month, "unknown season")
    lang_name = {
        "hi": "Hindi", "mr": "Marathi", "ta": "Tamil", "te": "Telugu",
        "bn": "Bengali", "kn": "Kannada", "pa": "Punjabi", "gu": "Gujarati",
    }.get(lang_code, "Hindi")

    return f"""You are an expert Indian agricultural scientist and agronomist with 20 years of experience advising smallholder farmers in India.

A farmer in {village}, {state} grows {crop}. Today is {datetime.now().strftime('%B %d, %Y')} — {season}.

LIVE SATELLITE DATA (from ISRO + NASA POWER right now):
- Soil Moisture:          {soil_moisture:.1f}%
- NDVI (crop greenness):  {ndvi:.2f}  (0=bare soil, 1=lush green)
- Rainfall last 7 days:   {rainfall_7d:.1f} mm
- Temperature max today:  {temp_max:.1f}°C
- Humidity:               {humidity:.0f}%
- Evapotranspiration:     {et0:.2f} mm/day

Your task:
1. Analyse the data as an expert would — consider crop-specific needs for {crop}, the season, and regional climate of {state}.
2. Identify the TOP issue the farmer faces right now (drought / pest risk / sowing window / no action needed).
3. Give ONE specific, actionable advisory in simple {lang_name} — no English, no jargon, no technical terms.
4. Maximum 3 sentences. Be direct. Address the farmer as "किसान भाई" (or regional equivalent).
5. End with one very specific action they should take TODAY or TOMORROW.

Respond ONLY in {lang_name}. No English. No explanation of your reasoning."""


def get_gemini_advisory(
    village: str, state: str, crop: str,
    soil_moisture: float, ndvi: float,
    rainfall_7d: float, temp_max: float,
    humidity: float, et0: float,
    lang_code: str = "hi",
) -> dict:
    """
    Call Gemini 2.0 Flash to generate an expert advisory.

    Returns:
        {
          "advisory": str,        # advisory text in requested language
          "source": str,          # "gemini" or "fallback"
          "model": str,
        }
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        logger.info("GEMINI_API_KEY not set — Gemini advisory unavailable")
        return {"advisory": "", "source": "not_configured", "model": "none"}

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        prompt = _build_prompt(
            village, state, crop,
            soil_moisture, ndvi, rainfall_7d,
            temp_max, humidity, et0, lang_code,
        )

        # Try models in order: 2.5-flash → 2.0-flash → 1.5-flash
        advisory_text = None
        model_used = None
        for model_name in ("models/gemini-2.5-flash", "models/gemini-2.0-flash", "models/gemini-flash-latest"):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                advisory_text = response.text.strip()
                model_used = model_name
                break
            except Exception as model_err:
                logger.warning("Model %s failed: %s", model_name, str(model_err)[:120])
                continue

        if not advisory_text:
            raise RuntimeError("All Gemini models exhausted quota or failed")

        logger.info("Gemini advisory generated (%d chars) for %s via %s", len(advisory_text), village, model_used)

        return {
            "advisory": advisory_text,
            "source": "gemini",
            "model": model_used,
        }

    except Exception as e:
        logger.error("Gemini API error for %s: %s", village, e)
        return {"advisory": "", "source": "error", "model": "none", "error": str(e)}


def get_gemini_pest_analysis(
    village: str, crop: str,
    temp_max: float, temp_min: float,
    humidity: float, ndvi: float,
    ndvi_7d_ago: float, rainfall_today: float,
    lang_code: str = "hi",
) -> dict:
    """
    Gemini-powered pest risk analysis — more nuanced than rule-based model.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        return {"advisory": "", "source": "not_configured"}

    ndvi_drop = round(ndvi_7d_ago - ndvi, 3)
    lang_name = {
        "hi": "Hindi", "mr": "Marathi", "ta": "Tamil", "te": "Telugu",
        "bn": "Bengali", "kn": "Kannada", "pa": "Punjabi", "gu": "Gujarati",
    }.get(lang_code, "Hindi")

    prompt = f"""You are an expert Indian plant pathologist and pest management specialist.

Farmer grows {crop} near {village}.

CURRENT CONDITIONS:
- Temperature: {temp_max:.1f}°C max, {temp_min:.1f}°C min
- Humidity: {humidity:.0f}%
- NDVI today: {ndvi:.2f}
- NDVI 7 days ago: {ndvi_7d_ago:.2f}  (change: {ndvi_drop:+.3f})
- Rainfall today: {rainfall_today:.1f} mm

Identify any pest or disease risk for {crop} given these conditions.
Respond in {lang_name} only, 2 sentences max. Name the specific pest/disease if risk exists, and say what to spray or do today.
If no risk, say so in one short sentence."""

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        pest_text = None
        pest_model = None
        for model_name in ("models/gemini-2.5-flash", "models/gemini-2.0-flash", "models/gemini-flash-latest"):
            try:
                response = client.models.generate_content(model=model_name, contents=prompt)
                pest_text = response.text.strip()
                pest_model = model_name
                break
            except Exception:
                continue
        if not pest_text:
            raise RuntimeError("All models failed")
        return {
            "advisory": pest_text,
            "source": "gemini",
            "model": pest_model,
        }
    except Exception as e:
        logger.error("Gemini pest analysis error: %s", e)
        return {"advisory": "", "source": "error", "error": str(e)}
