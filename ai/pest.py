"""
ai/pest.py
----------
Pest Risk Model — identifies pest threats based on temperature,
humidity, NDVI trends, and known pest ecology for Indian agriculture.

Covers major pests affecting Indian crops:
  - Aphid (sucking pest, cool-humid conditions)
  - Whitefly (warm, dry conditions)
  - Fungal Blight / Powdery Mildew (high humidity, moderate temp)
  - Stem Borer (warm, humid — paddy/sugarcane)
  - Locust / Armyworm (sudden NDVI drops)
  - Bollworm (cotton, specific temp range)
"""

from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
# Crop-specific pest vulnerability tables
# ─────────────────────────────────────────────────────────────────────────────

CROP_PEST_MAP = {
    "wheat":     ["aphid", "fungal_blight", "rust"],
    "rice":      ["stem_borer", "fungal_blight", "armyworm"],
    "paddy":     ["stem_borer", "fungal_blight", "armyworm"],
    "cotton":    ["bollworm", "whitefly", "aphid"],
    "sugarcane": ["stem_borer", "armyworm", "fungal_blight"],
    "groundnut": ["aphid", "fungal_blight", "whitefly"],
    "soybean":   ["whitefly", "aphid", "fungal_blight"],
    "bajra":     ["aphid", "armyworm", "rust"],
    "ragi":      ["aphid", "rust", "armyworm"],
    "grapes":    ["fungal_blight", "aphid", "whitefly"],
    "banana":    ["fungal_blight", "aphid", "armyworm"],
    "orange":    ["aphid", "fungal_blight", "whitefly"],
    "tea":       ["aphid", "fungal_blight", "armyworm"],
}


def pest_risk_model(
    temp_max: float,        # °C maximum temperature
    temp_min: float,        # °C minimum temperature
    humidity: float,        # % relative humidity
    ndvi: float,            # current NDVI
    ndvi_7d_ago: float,     # NDVI 7 days ago
    crop: str = "wheat",    # crop type
    rainfall_today: float = 0.0,  # mm rainfall today
) -> dict:
    """
    Evaluate pest threat for the given agro-meteorological conditions.
    Returns the highest-priority pest threat found.
    """
    ndvi_drop = ndvi_7d_ago - ndvi   # positive = vegetation declining
    crop_pests = CROP_PEST_MAP.get(crop.lower(), list(CROP_PEST_MAP["wheat"]))
    month = datetime.utcnow().month

    threats = []

    # ── Locust / Armyworm ─────────────────────────────────────────────────────
    # Sudden vegetation collapse: NDVI drop > 0.12 in a week is a red flag
    if "armyworm" in crop_pests or "locust" in crop_pests:
        if ndvi_drop > 0.15:
            threats.append({
                "pest": "Locust / Armyworm",
                "risk": "CRITICAL",
                "color": "red",
                "emoji": "🔴",
                "confidence": 0.90 if ndvi_drop > 0.2 else 0.75,
                "action": "Sudden crop damage detected. Contact your local Krishi Vigyan Kendra "
                          "(KVK) or agriculture officer immediately. Do not wait.",
                "action_hindi": "अचानक फसल क्षति। तुरंत कृषि अधिकारी से संपर्क करें।",
                "prevention": "Inspect fields now. Apply recommended pesticide at early stage.",
            })
        elif ndvi_drop > 0.08:
            threats.append({
                "pest": "Armyworm (early detection)",
                "risk": "HIGH",
                "color": "orange",
                "emoji": "🟠",
                "confidence": 0.65,
                "action": "NDVI declining rapidly. Inspect plants for caterpillar damage. "
                          "Spray chlorpyrifos or neem-based solution if infestation confirmed.",
                "action_hindi": "NDVI तेजी से गिर रहा है। खेत की तुरंत जांच करें।",
                "prevention": "Early morning field walk recommended today.",
            })

    # ── Bollworm (Cotton) ─────────────────────────────────────────────────────
    if "bollworm" in crop_pests:
        if 25 <= temp_max <= 35 and humidity > 60 and ndvi < 0.55:
            threats.append({
                "pest": "Bollworm (Pink/American)",
                "risk": "HIGH",
                "color": "orange",
                "emoji": "🟠",
                "confidence": 0.80,
                "action": "Peak bollworm conditions. Install pheromone traps. "
                          "Apply recommended Bt spray if larvae found. Check bolls daily.",
                "action_hindi": "बॉलवर्म का खतरा। फेरोमोन ट्रैप लगाएं।",
                "prevention": "Install 5 pheromone traps per hectare. Spray Bt if >5 larvae/plant.",
            })

    # ── Aphid ─────────────────────────────────────────────────────────────────
    if "aphid" in crop_pests:
        if 15 <= temp_max <= 28 and humidity > 65:
            confidence = min(0.9, 0.6 + (humidity - 65) / 100)
            threats.append({
                "pest": "Aphid",
                "risk": "MODERATE",
                "color": "yellow",
                "emoji": "🟡",
                "confidence": round(confidence, 2),
                "action": "Aphid risk conditions present. Check leaf undersides. "
                          "Spray neem oil (3ml/L) early morning this week.",
                "action_hindi": "माहू का खतरा। नीम का तेल (3ml/L) इस सप्ताह छिड़कें।",
                "prevention": "Spray neem oil or imidacloprid if infestation > 50 aphids/plant.",
            })

    # ── Whitefly ──────────────────────────────────────────────────────────────
    if "whitefly" in crop_pests:
        if temp_max > 30 and humidity < 60 and ndvi < 0.5:
            threats.append({
                "pest": "Whitefly",
                "risk": "MODERATE",
                "color": "yellow",
                "emoji": "🟡",
                "confidence": 0.70,
                "action": "Hot dry conditions favor whitefly. Use yellow sticky traps. "
                          "Avoid water stress — it increases whitefly severity.",
                "action_hindi": "सफेद मक्खी का खतरा। पीले चिपचिपे ट्रैप उपयोग करें।",
                "prevention": "Use reflective mulch. Spray spinosad if leaves show yellowing.",
            })

    # ── Stem Borer (Rice/Paddy/Sugarcane) ────────────────────────────────────
    if "stem_borer" in crop_pests:
        if 25 <= temp_max <= 35 and humidity > 75 and month in [6, 7, 8, 9]:
            threats.append({
                "pest": "Stem Borer",
                "risk": "HIGH" if humidity > 85 else "MODERATE",
                "color": "orange" if humidity > 85 else "yellow",
                "emoji": "🟠" if humidity > 85 else "🟡",
                "confidence": 0.75,
                "action": "Stem borer active season. Look for 'dead hearts' in young plants. "
                          "Use light traps at night. Apply cartap hydrochloride or chlorpyrifos.",
                "action_hindi": "तना छेदक सक्रिय मौसम। प्रकाश ट्रैप का उपयोग करें।",
                "prevention": "Remove and destroy affected tillers. Apply pheromone traps.",
            })

    # ── Fungal Blight / Rust ──────────────────────────────────────────────────
    if "fungal_blight" in crop_pests or "rust" in crop_pests:
        if humidity > 80 and temp_max < 28 and rainfall_today > 5:
            risk_level = "HIGH" if humidity > 88 else "MODERATE"
            threats.append({
                "pest": "Fungal Blight / Leaf Rust",
                "risk": risk_level,
                "color": "orange" if risk_level == "HIGH" else "yellow",
                "emoji": "🟠" if risk_level == "HIGH" else "🟡",
                "confidence": 0.80,
                "action": "High humidity after rain creates fungal risk. "
                          "Apply copper fungicide or mancozeb within 48 hours. "
                          "Avoid overhead irrigation.",
                "action_hindi": "बारिश के बाद फफूंद का खतरा। कॉपर फंगीसाइड 48 घंटे में लगाएं।",
                "prevention": "Ensure good air circulation. Spray propiconazole at leaf emergence.",
            })
        elif humidity > 72 and temp_max < 26:
            threats.append({
                "pest": "Powdery Mildew (early risk)",
                "risk": "LOW",
                "color": "lightgreen",
                "emoji": "🟢",
                "confidence": 0.55,
                "action": "Conditions marginally favorable for mildew. "
                          "Monitor leaves for white powder deposits.",
                "action_hindi": "फफूंद की संभावना। पत्तियों पर सफेद पाउडर की जांच करें।",
                "prevention": "Spray sulphur-based fungicide preventively if crop is susceptible.",
            })

    # ── Return highest-priority threat ───────────────────────────────────────
    if not threats:
        return {
            "pest": "None detected",
            "risk": "LOW",
            "color": "green",
            "emoji": "🟢",
            "confidence": 0.90,
            "action": "No pest threat detected. Continue normal monitoring. "
                      "Do a weekly field walk to catch early signs.",
            "action_hindi": "कोई कीट खतरा नहीं। सामान्य निगरानी जारी रखें।",
            "prevention": "Maintain field hygiene. Remove crop residues after harvest.",
        }

    # Priority order: CRITICAL > HIGH > MODERATE > LOW
    priority = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "LOW": 1}
    top_threat = max(threats, key=lambda x: priority.get(x["risk"], 0))
    top_threat["all_threats"] = [t["pest"] for t in threats]
    return top_threat
