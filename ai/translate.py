"""
ai/translate.py
---------------
Multilingual advisory engine for Indian languages.
Primary:  googletrans (free, no key, 500k chars/month)
Fallback: Hardcoded common agriculture phrases for offline use

Supported languages:
  hi = Hindi     mr = Marathi   ta = Tamil    te = Telugu
  bn = Bengali   kn = Kannada   pa = Punjabi  gu = Gujarati
  or = Odia      ml = Malayalam
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "hi": "Hindi",
    "mr": "Marathi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "kn": "Kannada",
    "pa": "Punjabi",
    "gu": "Gujarati",
    "or": "Odia",
    "ml": "Malayalam",
}

# ─────────────────────────────────────────────────────────────────────────────
# Pre-translated phrase bank (offline fallback)
# ─────────────────────────────────────────────────────────────────────────────

PHRASE_BANK = {
    "Irrigate today. Crop is severely stressed.": {
        "hi": "आज सिंचाई करें। फसल गंभीर तनाव में है।",
        "mr": "आज पाणी द्या. पिक गंभीर ताणात आहे.",
        "ta": "இன்று நீர்ப்பாசனம் செய்யுங்கள். பயிர் கடுமையான அழுத்தத்தில் உள்ளது.",
        "te": "నేడు నీరు పెట్టండి. పంట తీవ్ర ఒత్తిడిలో ఉంది.",
        "bn": "আজ সেচ দিন। ফসল মারাত্মক চাপে আছে।",
        "kn": "ಇಂದು ನೀರಾವರಿ ಮಾಡಿ. ಬೆಳೆ ತೀವ್ರ ಒತ್ತಡದಲ್ಲಿದೆ.",
        "pa": "ਅੱਜ ਸਿੰਚਾਈ ਕਰੋ। ਫਸਲ ਗੰਭੀਰ ਤਣਾਅ ਵਿੱਚ ਹੈ।",
        "gu": "આજે સિંચાઈ કરો. પાક ગંભીર તણાવમાં છે.",
    },
    "Irrigate within 2 days. Monitor closely.": {
        "hi": "2 दिन में सिंचाई करें। ध्यान से निगरानी करें।",
        "mr": "2 दिवसांत पाणी द्या. जवळून लक्ष ठेवा.",
        "ta": "2 நாட்களில் நீர்ப்பாசனம் செய்யுங்கள். கவனமாக கண்காணியுங்கள்.",
        "te": "2 రోజులలో నీరు పెట్టండి. జాగ్రత్తగా పర్యవేక్షించండి.",
        "bn": "2 দিনের মধ্যে সেচ দিন। ঘনিষ্ঠভাবে পর্যবেক্ষণ করুন।",
        "kn": "2 ದಿನಗಳಲ್ಲಿ ನೀರಾವರಿ ಮಾಡಿ. ಎಚ್ಚರಿಕೆಯಿಂದ ಮೇಲ್ವಿಚಾರಣೆ ಮಾಡಿ.",
        "pa": "2 ਦਿਨਾਂ ਵਿੱਚ ਸਿੰਚਾਈ ਕਰੋ। ਧਿਆਨ ਨਾਲ ਨਿਗਰਾਨੀ ਕਰੋ।",
        "gu": "2 દિવસમાં સિંચાઈ કરો. ધ્યાનથી નિરીક્ષણ કરો.",
    },
    "No irrigation needed. Crop is doing well.": {
        "hi": "सिंचाई की जरूरत नहीं। फसल अच्छी है।",
        "mr": "पाण्याची गरज नाही. पिक चांगले आहे.",
        "ta": "நீர்ப்பாசனம் தேவையில்லை. பயிர் நன்றாக வளர்கிறது.",
        "te": "నీరు పెట్టడం అవసరం లేదు. పంట బాగుంది.",
        "bn": "সেচের প্রয়োজন নেই। ফসল ভালো আছে।",
        "kn": "ನೀರಾವರಿ ಅಗತ್ಯವಿಲ್ಲ. ಬೆಳೆ ಚೆನ್ನಾಗಿ ಬೆಳೆಯುತ್ತಿದೆ.",
        "pa": "ਸਿੰਚਾਈ ਦੀ ਲੋੜ ਨਹੀਂ। ਫਸਲ ਚੰਗੀ ਹੈ।",
        "gu": "સિંચાઈ જરૂરી નથી. પાક સારો છે.",
    },
    "Spray neem oil solution this week.": {
        "hi": "इस सप्ताह नीम का तेल छिड़कें।",
        "mr": "या आठवड्यात कडुनिंब तेल फवारा.",
        "ta": "இந்த வாரம் வேப்பெண்ணெய் தெளிக்கவும்.",
        "te": "ఈ వారం వేపనూనె పిచికారీ చేయండి.",
        "bn": "এই সপ্তাহে নিম তেল স্প্রে করুন।",
        "kn": "ಈ ವಾರ ಬೇವಿನ ಎಣ್ಣೆ ಸಿಂಪಡಿಸಿ.",
        "pa": "ਇਸ ਹਫ਼ਤੇ ਨਿੰਮ ਦਾ ਤੇਲ ਛਿੜਕੋ।",
        "gu": "આ અઠવાડિયે લીમડાનું તેલ છાંટો.",
    },
    "Contact local agriculture officer immediately.": {
        "hi": "तुरंत स्थानीय कृषि अधिकारी से संपर्क करें।",
        "mr": "ताबडतोब स्थानिक कृषी अधिकाऱ्याशी संपर्क साधा.",
        "ta": "உடனே உள்ளூர் வேளாண் அதிகாரியை தொடர்பு கொள்ளவும்.",
        "te": "వెంటనే స్థానిక వ్యవసాయ అధికారిని సంప్రదించండి.",
        "bn": "অবিলম্বে স্থানীয় কৃষি কর্মকর্তার সাথে যোগাযোগ করুন।",
        "kn": "ತಕ್ಷಣ ಸ್ಥಳೀಯ ಕೃಷಿ ಅಧಿಕಾರಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ.",
        "pa": "ਤੁਰੰਤ ਸਥਾਨਕ ਖੇਤੀਬਾੜੀ ਅਧਿਕਾਰੀ ਨਾਲ ਸੰਪਰਕ ਕਰੋ।",
        "gu": "તાત્કાલિક સ્થાનિક કૃષિ અધિકારીનો સંપર્ક કરો.",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Translation Functions
# ─────────────────────────────────────────────────────────────────────────────

def translate_advisory(text: str, lang_code: str) -> str:
    """
    Translate advisory text to the given language.
    1. Check phrase bank for exact match.
    2. Try googletrans.
    3. Return original text as fallback.
    """
    if not text or lang_code == "en":
        return text

    if lang_code not in SUPPORTED_LANGUAGES:
        logger.warning("Unsupported language: %s", lang_code)
        return text

    # Fast path: phrase bank
    if text in PHRASE_BANK and lang_code in PHRASE_BANK[text]:
        return PHRASE_BANK[text][lang_code]

    # deep-translator path (Python 3.13+ compatible)
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source="en", target=lang_code).translate(text)
        return result or text
    except ImportError:
        logger.warning("deep-translator not installed — returning English")
        return text
    except Exception as e:
        logger.error("Translation failed for lang=%s: %s", lang_code, e)
        return text


# ─────────────────────────────────────────────────────────────────────────────
# Localised section labels — fixes Hindi-only headers for all 10 languages
# ─────────────────────────────────────────────────────────────────────────────

_SECTION_LABELS = {
    "hi": {"water": "पानी",     "pest": "कीट",   "sow": "बुआई"},
    "mr": {"water": "पाणी",     "pest": "कीड",   "sow": "पेरणी"},
    "ta": {"water": "நீர்",     "pest": "பூச்சி","sow": "விதைப்பு"},
    "te": {"water": "నీరు",     "pest": "పురుగు","sow": "విత్తనం"},
    "bn": {"water": "জল",       "pest": "পোকা",  "sow": "বপন"},
    "kn": {"water": "ನೀರು",     "pest": "ಕೀಟ",   "sow": "ಬಿತ್ತನೆ"},
    "pa": {"water": "ਪਾਣੀ",     "pest": "ਕੀੜਾ",  "sow": "ਬਿਜਾਈ"},
    "gu": {"water": "પાણી",     "pest": "જીવાત", "sow": "વાવણી"},
    "or": {"water": "ଜଳ",       "pest": "ପୋକ",   "sow": "ବୁଣିବା"},
    "ml": {"water": "വെള്ളം",   "pest": "കീടം",  "sow": "വിതയ്ക്കൽ"},
    "en": {"water": "Water",    "pest": "Pest",  "sow": "Sowing"},
}


def build_full_advisory(
    drought: dict,
    pest: dict,
    sowing: dict,
    lang_code: str = "hi",
    village_name: str = "",
    crop: str = "",
) -> str:
    """
    Build a complete WhatsApp/SMS-ready advisory in the given language.
    Section labels (Water / Pest / Sowing) are localised per language.
    """
    lbl = _SECTION_LABELS.get(lang_code, _SECTION_LABELS["hi"])
    lines = []

    header = f"🌾 KISAN AI — {village_name}" if village_name else "🌾 KISAN AI"
    if crop:
        header += f" ({crop.capitalize()})"
    lines.append(header)
    lines.append("")

    # Drought
    drought_icon = drought.get("emoji", "")
    drought_level = drought.get("level", "")
    drought_action = drought.get("action", "")
    lines.append(f"💧 {lbl['water']}: {drought_icon} {drought_level}")
    lines.append(translate_advisory(drought_action, lang_code))
    lines.append("")

    # Pest
    pest_icon = pest.get("emoji", "")
    pest_name = pest.get("pest", "")
    pest_risk = pest.get("risk", "")
    pest_action = pest.get("action", "")
    lines.append(f"🐛 {lbl['pest']}: {pest_icon} {pest_name} ({pest_risk})")
    lines.append(translate_advisory(pest_action, lang_code))
    lines.append("")

    # Sowing
    sow_icon = sowing.get("emoji", "")
    sow_decision = sowing.get("decision", "")
    sow_action = sowing.get("action", "")
    lines.append(f"🌱 {lbl['sow']}: {sow_icon} {sow_decision}")
    lines.append(translate_advisory(sow_action, lang_code))
    lines.append("")

    lines.append("📡 ISRO + NASA satellite data | kisan.ai")

    return "\n".join(lines)
