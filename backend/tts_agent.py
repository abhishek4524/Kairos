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
#   avatar.vrm  → Kavya   — warm, neutral Indian female
#   avatar1.vrm → Shriya  — slightly sharper/faster (sarcasm needs a quicker delivery)
#   avatar2.vrm → Kumar   — measured male, slightly slower for thoughtful tone
#   avatar3.vrm → Lucy    — high-pitch, fast — maximum energy
#   avatar4.vrm → Sara    — low-pitch, slow — calming, soothing
#   avatar5.vrm → Aanya   — child voice (AnaNeural), highest pitch
#   avatar6.vrm → Ankur   — chill male, slightly upbeat
AVATAR_VOICE_CONFIG = {
    "avatar.vrm": {   # Kavya — warm, natural
        "voice_hi": "hi-IN-SwaraNeural",
        "voice_en": "en-IN-NeerjaNeural",
        "pitch": 0, "rate": +15,
    },
    "avatar1.vrm": {  # Shriya — sharper, quicker; sarcasm lands better with pace
        "voice_hi": "hi-IN-SwaraNeural",
        "voice_en": "en-IN-NeerjaNeural",
        "pitch": +15, "rate": +20,
    },
    "avatar2.vrm": {  # Kumar — deep male, deliberate pace
        "voice_hi": "hi-IN-MadhurNeural",
        "voice_en": "en-IN-PrabhatNeural",
        "pitch": -5, "rate": +5,
    },
    "avatar3.vrm": {  # Lucy — highest energy: fast, bright, loud
        "voice_hi": "hi-IN-SwaraNeural",
        "voice_en": "en-US-AriaNeural",
        "pitch": +30, "rate": +35,
    },
    "avatar4.vrm": {  # Sara — cute girl voice
        "voice_hi": "hi-IN-SwaraNeural",
        "voice_en": "en-US-AnaNeural",
        "pitch": +20, "rate": +20,
    },
    "avatar5.vrm": {  # Aanya — child voice (AnaNeural), very high pitch
        "voice_hi": "hi-IN-SwaraNeural",
        "voice_en": "en-US-AnaNeural",
        "pitch": +50, "rate": +25,
    },
    "avatar6.vrm": {  # Ankur — chill male, slightly easy-going pace
        "voice_hi": "hi-IN-MadhurNeural",
        "voice_en": "en-IN-PrabhatNeural",
        "pitch": +5, "rate": +15,
    },
}

def _get_edge_voice(text: str, language: str, avatar: str = "avatar.vrm") -> tuple[str, int, int]:
    config = AVATAR_VOICE_CONFIG.get(avatar, AVATAR_VOICE_CONFIG["avatar.vrm"])
    
    is_hindi = False
    for ch in text:
        cp = ord(ch)
        if 0x0900 <= cp <= 0x097F:   # Devanagari
            is_hindi = True
            break
            
    voice = config["voice_hi"] if (is_hindi or language == "hi") else config["voice_en"]
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
    
    # Apply dynamic Voice Tone Variation based on emotion tags
    if emotion in ["happy", "jollyLaughter", "excited"]:
        rate_val += 12
        pitch_val += 15
    elif emotion in ["sad", "comforting", "thoughtfulness"]:
        rate_val -= 15
        pitch_val -= 10
    elif emotion == "thinking":
        rate_val -= 10
    elif emotion in ["surprised", "surprise"]:
        rate_val += 15
        pitch_val += 20
    elif emotion in ["anger", "displeasure"]:
        rate_val += 20
        pitch_val -= 15 # Lower pitch but much faster/louder feel
    elif emotion in ["annoyed", "disagreement"]:
        rate_val -= 5
        pitch_val -= 10 # Flat and unamused
    elif emotion in ["confidentSpeech", "leadership", "presentation"]:
        rate_val += 5
        pitch_val += 5 # Crisp and clear
    elif emotion in ["coySmile", "blushing", "receptive"]:
        rate_val -= 10
        pitch_val += 10 # Soft, slightly higher and slower
        
        
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
