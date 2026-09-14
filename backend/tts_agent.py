import os
import io
import asyncio
from pydub import AudioSegment
import platform
import shutil
import edge_tts

# ── Point pydub at the bundled ffmpeg in tools/ or system ffmpeg ───────────────
_TOOLS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "tools"))

if platform.system() == "Windows":
    _FFMPEG = os.path.join(_TOOLS_DIR, "ffmpeg.exe")
else:
    _FFMPEG = os.path.join(_TOOLS_DIR, "ffmpeg")

if not os.path.exists(_FFMPEG):
    _FFMPEG_SYS = shutil.which("ffmpeg")
    if _FFMPEG_SYS:
        _FFMPEG = _FFMPEG_SYS

if _FFMPEG and os.path.exists(_FFMPEG):
    AudioSegment.converter = _FFMPEG
    AudioSegment.ffmpeg    = _FFMPEG
    if _TOOLS_DIR in _FFMPEG:
        os.environ["PATH"]     = _TOOLS_DIR + os.pathsep + os.environ.get("PATH", "")
    print(f"[TTS] Using ffmpeg: {_FFMPEG}")
else:
    print("[TTS] ffmpeg not found in tools/ or system PATH")

# ── High-Quality Female Neural Voices Configuration (Arya) ────────────────────
# Primary English Female: en-US-AvaNeural (Natural, crisp AI female voice)
# Hindi/Hinglish Female: hi-IN-SwaraNeural (Natural Hindi Female — handles Hinglish naturally)
VOICE_MAP = {
    "en": "en-US-AvaNeural",
    "hi": "hi-IN-SwaraNeural",
    "hinglish": "hi-IN-SwaraNeural",   # Hindi neural voice handles Hinglish without bad accent
    "ur": "ur-PK-UzmaNeural",
    "ar": "ar-SA-ZariyahNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "es": "es-ES-ElviraNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "pt": "pt-BR-FranciscaNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "it": "it-IT-ElsaNeural",
    "tr": "tr-TR-EmelNeural",
    "ta": "ta-IN-PallaviNeural",
    "te": "te-IN-ShrutiNeural",
    "bn": "bn-IN-TanishaaNeural",
}
DEFAULT_VOICE = "en-US-AvaNeural"  # English female (Arya) default — responses always in English

def _get_edge_voice(language: str = "en") -> tuple[str, int, int]:
    voice = VOICE_MAP.get(language, DEFAULT_VOICE)
    # Pitch: +0Hz, Rate: +0% for natural human cadence
    return voice, 0, 0

# ─────────────────────────────────────────────────────────────────────────────
# Edge-TTS generator with SSML emotional prosody
# ─────────────────────────────────────────────────────────────────────────────

from tts_emotion_profiles import get_emotion_profile


def _build_ssml(text: str, voice: str, emotion: str = "neutral") -> str:
    """
    Wraps text in Edge-TTS compatible SSML with prosody tags and micro-pauses.
    Falls back to neutral profile if emotion is unrecognized.
    """
    profile = get_emotion_profile(emotion)
    rate   = profile["rate"]
    pitch  = profile["pitch"]
    volume = profile["volume"]

    # Escape XML reserved characters
    safe_text = (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
    )

    # Insert natural human micro-pauses at punctuation boundaries
    safe_text = (
        safe_text.replace(", ", ', <break time="120ms"/> ')
                 .replace(". ", '. <break time="180ms"/> ')
    )

    ssml = (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">'
        f'<voice name="{voice}">'
        f'<prosody rate="{rate}" pitch="{pitch}" volume="{volume}">'
        f'{safe_text}'
        '</prosody>'
        '</voice>'
        '</speak>'
    )
    return ssml


async def _generate_edge_audio(
    text: str,
    language: str = "en",
    emotion: str = "neutral",
) -> bytes:
    """Generates audio via Edge-TTS with emotional prosody (rate, pitch, volume) applied."""
    voice, _base_pitch, _base_rate = _get_edge_voice(language)
    profile = get_emotion_profile(emotion)

    rate   = profile["rate"]
    pitch  = profile["pitch"]
    volume = profile["volume"]

    print(
        f"[EDGE-TTS Male] voice={voice}, lang={language}, emotion={emotion}, "
        f"rate={rate}, pitch={pitch}, volume={volume}"
    )

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
        volume=volume,
    )
    byte_io = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            byte_io.write(chunk["data"])
    audio_bytes = byte_io.getvalue()

    if not audio_bytes:
        # Fallback: try plain text with default neutral prosody rather than failing
        print(f"[EDGE-TTS] Prosody generation returned 0 bytes (emotion={emotion}), retrying with default neutral...")
        communicate_plain = edge_tts.Communicate(text=text, voice=voice, rate="+10%", pitch="+0Hz", volume="+0%")
        byte_io2 = io.BytesIO()
        async for chunk in communicate_plain.stream():
            if chunk["type"] == "audio":
                byte_io2.write(chunk["data"])
        audio_bytes = byte_io2.getvalue()

    if not audio_bytes:
        raise RuntimeError(f"Edge-TTS returned 0 bytes for voice={voice}, emotion={emotion}")

    return audio_bytes


# ─────────────────────────────────────────────────────────────────────────────
# Main async TTS function (returns audio_bytes)
# ─────────────────────────────────────────────────────────────────────────────
async def generate_audio_async(
    text: str,
    language: str = "en",
    emotion: str = "neutral",
    avatar: str = "kavya",
) -> tuple[bytes, None]:
    """
    High-quality voice generation with fallback chain:
      1. ElevenLabs TTS (if ELEVENLABS_API_KEY is set)
      2. Edge-TTS (Microsoft Neural — online)
      3. Piper TTS (offline fallback)

    Returns (audio_bytes, None) for backward-compatible call signatures.
    """
    try:
        from core import connectivity
        is_offline = connectivity.current_state().value == "OFFLINE"
    except Exception:
        is_offline = False

    if os.getenv("KAIROS_FORCE_OFFLINE", "0").lower() in ("1", "true", "yes"):
        is_offline = True

    if is_offline:
        print(f"[TTS] OFFLINE state active → synthesizing via Piper TTS (emotion={emotion})")
        from providers import piper_tts
        audio_bytes, _ = await piper_tts.synthesize_offline(text, language=language, emotion=emotion)
        return audio_bytes, None

    # ── Step 1: ElevenLabs TTS (best quality) ─────────────────────────────────
    from providers import elevenlabs_tts
    if elevenlabs_tts.is_configured():
        try:
            audio_bytes = await elevenlabs_tts.synthesize(text, language=language)
            print(f"[TTS] ElevenLabs → {len(audio_bytes)} bytes")
            return audio_bytes, None
        except Exception as el_err:
            print(f"[TTS] ElevenLabs failed ({el_err}) → falling back to Edge-TTS")

    # ── Step 2: Edge-TTS (Microsoft Neural) ───────────────────────────────────
    try:
        audio_bytes = await _generate_edge_audio(text, language, emotion)
        return audio_bytes, None
    except Exception as edge_err:
        print(f"[TTS] Edge-TTS failed ({edge_err}) → falling back to Piper TTS")

    # ── Step 3: Piper TTS (offline) ───────────────────────────────────────────
    from providers import piper_tts
    audio_bytes, _ = await piper_tts.synthesize_offline(text, language=language, emotion=emotion)
    return audio_bytes, None



