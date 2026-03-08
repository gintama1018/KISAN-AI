"""
ai/voice.py
-----------
KISAN AI — Voice Alert Engine

Converts Hindi/regional advisory text → audio → WhatsApp voice message.

Pipeline:
  1. ElevenLabs eleven_multilingual_v2 → generate MP3 from text
  2. Save to static/audio/ (served by Flask)
  3. Twilio WhatsApp media_url → sends voice note to farmer

Free tier:
  ElevenLabs: 10,000 characters/month free
  Get key: https://elevenlabs.io → Sign up → Profile → API Key

Why this matters:
  40% of Indian farmers are illiterate — a WhatsApp text does nothing.
  A voice message in their own dialect does everything.
"""

import os
import logging
import hashlib
import time

logger = logging.getLogger(__name__)

# Directory where audio files are saved (served at /static/audio/)
_AUDIO_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "audio")


def _ensure_audio_dir():
    os.makedirs(_AUDIO_DIR, exist_ok=True)


def _text_to_filename(text: str, lang: str) -> str:
    """Generate a stable filename from text hash so we cache repeated alerts."""
    h = hashlib.md5(f"{lang}:{text}".encode()).hexdigest()[:12]
    return f"kisan_{h}.mp3"


def _get_cached_twilio_url(filename: str) -> str:
    """Return previously uploaded Twilio URL for this file, or empty string."""
    url_cache = os.path.join(_AUDIO_DIR, filename.replace(".mp3", ".url"))
    if os.path.exists(url_cache):
        with open(url_cache) as f:
            return f.read().strip()
    return ""


def _save_cached_twilio_url(filename: str, url: str):
    _ensure_audio_dir()
    url_cache = os.path.join(_AUDIO_DIR, filename.replace(".mp3", ".url"))
    with open(url_cache, "w") as f:
        f.write(url)


def _upload_to_twilio_assets(mp3_path: str, filename: str,
                              account_sid: str, auth_token: str) -> str:
    """
    Upload an MP3 to Twilio Serverless Assets and return its public HTTPS URL.

    Each audio file gets its own Twilio Service (named by hash) so builds
    never conflict.  URL is ~60 s to provision on first call; subsequent
    calls return instantly from the .url cache file.

    Returns a URL like: https://kisanai-abc123.twil.io/kisan_abc123.mp3
    """
    import requests as req
    from requests.auth import HTTPBasicAuth

    auth = HTTPBasicAuth(account_sid, auth_token)
    base   = "https://serverless.twilio.com/v1"
    upload = "https://serverless-upload.twilio.com/v1"

    hash_part    = filename.replace("kisan_", "").replace(".mp3", "")  # e.g. 044525843d3f
    service_name = f"kisanai-{hash_part}"                              # unique per file

    # ── Step 1: Create Service (or fetch existing) ──────────────────────
    r = req.post(f"{base}/Services", auth=auth, data={
        "UniqueName": service_name,
        "FriendlyName": f"Kisan AI Audio {hash_part}",
        "IncludeCredentials": "false",
    })
    svc = r.json()
    if r.status_code in (400, 409) or "code" in svc:
        # Already exists — find it
        r2 = req.get(f"{base}/Services", auth=auth)
        service_sid = next(
            s["sid"] for s in r2.json().get("services", [])
            if s["unique_name"] == service_name
        )
    else:
        service_sid = svc["sid"]
    logger.info("Twilio Service SID: %s", service_sid)

    # ── Step 2: Create Asset ─────────────────────────────────────────────
    r = req.post(f"{base}/Services/{service_sid}/Assets", auth=auth,
                 data={"FriendlyName": filename})
    asset_sid = r.json()["sid"]

    # ── Step 3: Upload Asset Version (binary multipart) ──────────────────
    with open(mp3_path, "rb") as fh:
        r = req.post(
            f"{upload}/Services/{service_sid}/Assets/{asset_sid}/Versions",
            auth=auth,
            data={"Path": f"/{filename}", "Visibility": "public"},
            files={"Content": (filename, fh, "audio/mpeg")},
        )
    version_sid = r.json()["sid"]
    logger.info("Asset Version SID: %s", version_sid)

    # ── Step 4: Create Environment ───────────────────────────────────────
    r = req.post(f"{base}/Services/{service_sid}/Environments", auth=auth,
                 data={"UniqueName": "production", "DomainSuffix": hash_part[:14]})
    env_data = r.json()
    if "code" in env_data:          # already exists
        r2 = req.get(f"{base}/Services/{service_sid}/Environments", auth=auth)
        env_data = r2.json()["environments"][0]
    env_sid     = env_data["sid"]
    domain_name = env_data["domain_name"]
    logger.info("Environment domain: %s", domain_name)

    # ── Step 5: Create Build ─────────────────────────────────────────────
    r = req.post(f"{base}/Services/{service_sid}/Builds", auth=auth,
                 data={"AssetVersions": version_sid})
    build_sid = r.json()["sid"]

    # ── Step 6: Poll until build completes (max ~90 s) ───────────────────
    import time
    for attempt in range(30):
        time.sleep(3)
        r = req.get(f"{base}/Services/{service_sid}/Builds/{build_sid}/Status", auth=auth)
        status = r.json().get("status", "in_progress")
        logger.info("Build status [%d]: %s", attempt, status)
        if status == "completed":
            break
        if status == "failed":
            raise RuntimeError(f"Twilio build failed: {r.json()}")

    # ── Step 7: Deploy ───────────────────────────────────────────────────
    req.post(
        f"{base}/Services/{service_sid}/Environments/{env_sid}/Deployments",
        auth=auth, data={"BuildSid": build_sid},
    )

    public_url = f"https://{domain_name}/{filename}"
    logger.info("Twilio Assets URL ready: %s", public_url)
    return public_url


def generate_voice_alert(text: str, lang_code: str = "hi") -> dict:
    """
    Convert advisory text to MP3 using ElevenLabs eleven_multilingual_v2.

    Returns:
        {
          "success": bool,
          "file_path": str,      # absolute path to mp3
          "filename": str,       # e.g. kisan_abc123.mp3
          "source": str,         # "elevenlabs" or "error"
          "chars_used": int,
        }
    """
    api_key = os.getenv("ELEVENLABS_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        logger.info("ELEVENLABS_API_KEY not set — voice alerts disabled")
        return {"success": False, "source": "not_configured"}

    _ensure_audio_dir()
    filename = _text_to_filename(text, lang_code)
    file_path = os.path.join(_AUDIO_DIR, filename)

    # Return cached file if it already exists (avoids burning free quota)
    if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
        logger.info("Voice cache hit: %s", filename)
        return {
            "success": True,
            "file_path": file_path,
            "filename": filename,
            "source": "cache",
            "chars_used": 0,
        }

    # ElevenLabs voice IDs — Rachel works well for Hindi/multilingual
    # Other options: "pNInz6obpgDQGcFmaJgB" (Adam), "EXAVITQu4vr4xnSDxMaL" (Bella)
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel

    try:
        import requests as req

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.55,
                "similarity_boost": 0.75,
                "style": 0.3,
                "use_speaker_boost": True,
            },
        }

        r = req.post(url, json=payload, headers=headers, timeout=30)

        if r.status_code == 200:
            with open(file_path, "wb") as f:
                f.write(r.content)
            logger.info("Voice generated: %s (%d bytes)", filename, len(r.content))
            return {
                "success": True,
                "file_path": file_path,
                "filename": filename,
                "source": "elevenlabs",
                "chars_used": len(text),
            }
        else:
            err = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:200]
            logger.error("ElevenLabs error %d: %s", r.status_code, err)
            return {"success": False, "source": "error", "status_code": r.status_code, "error": str(err)}

    except Exception as e:
        logger.error("Voice generation failed: %s", e)
        return {"success": False, "source": "error", "error": str(e)}


def send_whatsapp_voice(
    advisory_text: str,
    to_number: str,
    lang_code: str = "hi",
    public_base_url: str = "",
) -> dict:
    """
    Full pipeline: text → ElevenLabs MP3 → Twilio WhatsApp voice note.

    Args:
        advisory_text:  The Hindi/regional advisory to speak
        to_number:      Farmer phone in E.164 format (+919876543210)
        lang_code:      Language of the text
        public_base_url: Public URL where Flask is hosted (e.g. https://kisan.ai)
                         Required for Twilio media_url. Use ngrok for local testing.

    Returns:
        {"status": "sent"|"error"|"demo", "sid": str, ...}
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    if not account_sid or account_sid.startswith("your_"):
        return {"status": "demo", "message": "Twilio not configured"}

    # Step 1: Generate voice
    voice_result = generate_voice_alert(advisory_text, lang_code)

    if not voice_result.get("success"):
        logger.warning("Voice generation failed, falling back to text WhatsApp")
        return _send_text_whatsapp(advisory_text, to_number, account_sid, auth_token, from_number)

    filename = voice_result["filename"]
    file_path = voice_result["file_path"]

    # Step 2: Get public URL — cache → Twilio Assets → PUBLIC_BASE_URL → text fallback
    media_url = _get_cached_twilio_url(filename)

    if not media_url:
        # Try Twilio Assets (zero extra service, ~60 s on first call)
        try:
            logger.info("Uploading %s to Twilio Assets...", filename)
            media_url = _upload_to_twilio_assets(file_path, filename, account_sid, auth_token)
            _save_cached_twilio_url(filename, media_url)
        except Exception as e:
            logger.warning("Twilio Assets upload failed (%s), trying PUBLIC_BASE_URL", e)
            # Fallback: PUBLIC_BASE_URL > RENDER_EXTERNAL_URL (auto-set by Render) > passed param
            base = (
                os.getenv("PUBLIC_BASE_URL")
                or os.getenv("RENDER_EXTERNAL_URL")   # Render sets this automatically
                or public_base_url
            )
            if base:
                media_url = f"{base.rstrip('/')}/static/audio/{filename}"
            else:
                logger.warning("No public URL available — sending text WhatsApp")
                return _send_text_whatsapp(advisory_text, to_number, account_sid, auth_token, from_number)

    # Step 3: Send via Twilio with audio attachment
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            from_=from_number,
            to=f"whatsapp:{to_number}",
            body="🌾 Kisan AI — आपकी फसल के लिए आवाज़ सलाह सुनें:",
            media_url=[media_url],
        )
        return {
            "status": "sent",
            "sid": message.sid,
            "type": "voice",
            "audio_url": media_url,
            "chars_generated": voice_result.get("chars_used", 0),
        }
    except Exception as e:
        logger.error("Twilio voice send failed: %s", e)
        return {"status": "error", "error": str(e)}


def _send_text_whatsapp(text: str, to_number: str,
                         account_sid: str, auth_token: str, from_number: str) -> dict:
    """Fallback: send plain text WhatsApp."""
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            from_=from_number,
            to=f"whatsapp:{to_number}",
            body=text,
        )
        return {"status": "sent", "sid": message.sid, "type": "text"}
    except Exception as e:
        logger.error("Twilio text send failed: %s", e)
        return {"status": "error", "error": str(e)}
