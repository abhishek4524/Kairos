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

# ── High-Quality Male Neural Voices Configuration ──────────────────────────────
# Primary English Male: en-US-ChristopherNeural (Authoritative, natural, crisp, intelligent AI voice)
# Secondary / Regional Male: en-IN-PrabhatNeural (Indian English Male)
# Hindi Male: hi-IN-MadhurNeural (Natural Hindi Male)
VOICE_MAP = {
    "en": "en-US-ChristopherNeural",
    "hi": "hi-IN-MadhurNeural",
    "ur": "ur-PK-AsadNeural",
    "ar": "ar-SA-HamedNeural",
    "fr": "fr-FR-HenriNeural",
    "de": "de-DE-ConradNeural",
    "es": "es-ES-AlvaroNeural",
    "ja": "ja-JP-KeitaNeural",
    "ko": "ko-KR-InJoonNeural",
    "zh": "zh-CN-YunxiNeural",
    "pt": "pt-BR-AntonioNeural",
    "ru": "ru-RU-DmitryNeural",
    "it": "it-IT-DiegoNeural",
    "tr": "tr-TR-AhmetNeural",
    "ta": "ta-IN-ValluvarNeural",
    "te": "te-IN-MohanNeural",
    "bn": "bn-IN-BashkarNeural",
}
DEFAULT_VOICE = "en-US-ChristopherNeural"

def _get_edge_voice(language: str = "en") -> tuple[str, int, int]:
    voice = VOICE_MAP.get(language, DEFAULT_VOICE)
    # Pitch: +0Hz, Rate: +10% for crisp, responsive AI assistant cadence
    return voice, 0, +10

# ─────────────────────────────────────────────────────────────────────────────
# Edge-TTS generator with SSML emotional prosody
# ─────────────────────────────────────────────────────────────────────────────

from tts_emotion_profiles import get_emotion_profile


def _build_ssml(text: str, voice: str, emotion: str = "neutral") -> str:
    """
    Wraps text in Edge-TTS compatible SSML with prosody tags from the emotion profile.
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
    Edge-TTS high-quality male voice generation with SSML emotional prosody.
    Returns (audio_bytes, None) for backward-compatible call signatures.

    emotion: any label from tts_emotion_profiles.EMOTION_PROFILES.
             Unrecognized labels silently fall back to 'neutral'.
    """
    audio_bytes = await _generate_edge_audio(text, language, emotion)
    return audio_bytes, None

