import os
import io
import asyncio
from pydub import AudioSegment

import platform
import shutil

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
    print("[TTS] ffmpeg not found in tools/ or system PATH — will send WAV (no MP3 encoding needed)")

# ── Chatterbox-TTS Initialization ──────────────────────────────────────────────
# (Chatterbox local TTS engine has been completely removed in favor of Edge-TTS)
CHATTERBOX_AVAILABLE = False
chatterbox_model = None
CHATTERBOX_SR = 24000

# ── Edge-TTS (fallback) ────────────────────────────────────────────────────────
import edge_tts

# Voice map: Whisper language code → Edge-TTS neural voice
VOICE_MAP = {
    "hi": "hi-IN-SwaraNeural",
    "en": "en-IN-NeerjaNeural",
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
DEFAULT_VOICE = "en-IN-NeerjaNeural"

# Per-character voice config.
# voice_hi  → Edge-TTS voice used when Devanagari script or lang==hi is detected
# voice_en  → Edge-TTS voice used for English / Hinglish / default
# pitch     → baseline Hz offset  (e.g. +30 = higher, -15 = deeper)
# rate      → baseline % speed offset (e.g. +20 = faster, -10 = slower)
#
# Character mapping:
def _get_edge_voice(text: str, language: str, avatar: str = "avatar.vrm") -> tuple[str, int, int]:
    config = {
        "voice_hi": "hi-IN-SwaraNeural",
        "voice_en": "en-IN-NeerjaNeural",
        "pitch": 0, "rate": +15,
    }
    # LLM output is now strictly enforced to be English, so we always use the English voice
    voice = config["voice_en"]
    return voice, config["pitch"], config["rate"]


# ─────────────────────────────────────────────────────────────────────────────
# Fallback Visemes Generator
# ─────────────────────────────────────────────────────────────────────────────
def _generate_fallback_visemes(duration: float) -> dict:
    pattern = ["X", "A", "C", "B", "D", "C", "E", "B", "C", "A", "D", "C", "B", "X"]
    cue_ms = 0.075
    cues = [{"start": 0.0, "end": 0.04, "value": "X"}]
    t = 0.04
    i = 0
    while t < duration - 0.05:
        v = pattern[i % len(pattern)]
        end = round(min(t + cue_ms, duration - 0.04), 3)
        cues.append({"start": round(t, 3), "end": end, "value": v})
        t = end
        i += 1
    cues.append({"start": round(t, 3), "end": round(duration, 3), "value": "X"})
    return {"metadata": {"soundFile": "", "duration": duration}, "mouthCues": cues}


# ─────────────────────────────────────────────────────────────────────────────
# Edge-TTS generator (fallback)
# ─────────────────────────────────────────────────────────────────────────────
async def _generate_edge_audio(text: str, language: str, emotion: str = "neutral", avatar: str = "avatar.vrm") -> tuple[bytes, dict]:
    voice, base_pitch, base_rate = _get_edge_voice(text, language, avatar)
    
    rate_val = base_rate
    pitch_val = base_pitch
    
    # Apply dynamic Voice Tone Variation based on emotion tags for rich vocal expressiveness
    if emotion in ["happy", "jollyLaughter", "excited", "approval"]:
        rate_val += 18
        pitch_val += 22
    elif emotion in ["sad", "comforting", "thoughtfulness", "calm"]:
        rate_val -= 10
        pitch_val -= 5
    elif emotion in ["thinking", "focused"]:
        rate_val -= 8
        pitch_val -= 2
    elif emotion in ["surprised", "surprise", "interestedFlash"]:
        rate_val += 20
        pitch_val += 28
    elif emotion in ["anger", "displeasure", "opposition"]:
        rate_val += 22
        pitch_val -= 18
    elif emotion in ["annoyed", "disagreement"]:
        rate_val -= 4
        pitch_val -= 12
    elif emotion in ["confidentSpeech", "leadership", "presentation", "confident"]:
        rate_val += 12
        pitch_val += 10
    elif emotion in ["coySmile", "blushing", "receptive", "friendlyContact", "greeting"]:
        rate_val += 6
        pitch_val += 14
    elif emotion in ["casualChat", "relaxed", "openPosture", "openness"]:
        rate_val += 4
        pitch_val += 6
        
        
    rate = f"{rate_val:+}%"
    pitch = f"{pitch_val:+}Hz"
        
    print(f"[EDGE-TTS] voice={voice}, lang={language}, emotion={emotion}, avatar={avatar}, rate={rate}, pitch={pitch}")
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    byte_io = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            byte_io.write(chunk["data"])
    audio_bytes = byte_io.getvalue()
    if not audio_bytes:
        raise RuntimeError(f"Edge-TTS returned 0 bytes for voice={voice}")

    def get_dur():
        seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        return len(seg) / 1000.0

    dur = await asyncio.to_thread(get_dur)
    return audio_bytes, _generate_fallback_visemes(dur)


# ─────────────────────────────────────────────────────────────────────────────
# Main async TTS function
# ─────────────────────────────────────────────────────────────────────────────
async def generate_audio_async(text: str, language: str = "en", emotion: str = "neutral", avatar: str = "avatar.vrm") -> tuple[bytes, dict]:
    """
    Edge-TTS (Fast & reliable for real-time)
    """
    return await _generate_edge_audio(text, language, emotion, avatar)
