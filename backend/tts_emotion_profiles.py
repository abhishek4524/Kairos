"""
tts_emotion_profiles.py — Edge-TTS SSML Prosody Profiles for Emotional TTS.

Maps emotion labels to Edge-TTS SSML prosody parameters:
  rate:   e.g. "+20%", "-10%", "+0%"
  pitch:  e.g. "+2Hz", "-3Hz", "+0Hz"
  volume: e.g. "+10%", "-15%", "+0%"

Add new emotions here without touching core TTS logic.
Unrecognized emotions fall back to the "neutral" profile.
"""

from typing import TypedDict


class EmotionProfile(TypedDict):
    rate: str        # Edge-TTS prosody rate delta  e.g. "+15%"
    pitch: str       # Edge-TTS prosody pitch delta e.g. "+2Hz"
    volume: str      # Edge-TTS prosody volume      e.g. "+0%"
    description: str # Human-readable description


# ── Emotion → SSML Prosody Parameter Map ─────────────────────────────────────
#
# en-US-ChristopherNeural verified SSML support:
#   <prosody rate="..." pitch="..." volume="...">
#   rate   : relative % e.g. "+20%", "-15%", "+0%"
#   pitch  : Hz delta    e.g. "+3Hz", "-4Hz", "+0Hz"
#   volume : relative % e.g. "+10%", "-20%", "+0%"
#
EMOTION_PROFILES: dict[str, EmotionProfile] = {
    # ── Neutral / Default ────────────────────────────────────────────────────
    "neutral": {
        "rate": "+10%",
        "pitch": "+0Hz",
        "volume": "+0%",
        "description": "Calm, balanced, standard assistant cadence",
    },

    # ── Positive / High Energy ───────────────────────────────────────────────
    "excited": {
        "rate": "+30%",
        "pitch": "+4Hz",
        "volume": "+8%",
        "description": "Faster, higher-pitched, louder — enthusiasm and energy",
    },
    "happy": {
        "rate": "+18%",
        "pitch": "+3Hz",
        "volume": "+5%",
        "description": "Upbeat, slightly faster, warm tone",
    },
    "enthusiastic": {
        "rate": "+25%",
        "pitch": "+3Hz",
        "volume": "+6%",
        "description": "Energetic and engaged",
    },
    "cheerful": {
        "rate": "+15%",
        "pitch": "+2Hz",
        "volume": "+4%",
        "description": "Light, bright and friendly",
    },

    # ── Calm / Reassuring ────────────────────────────────────────────────────
    "calm": {
        "rate": "-12%",
        "pitch": "-2Hz",
        "volume": "-5%",
        "description": "Slower, slightly lower pitch, measured — peaceful and grounding",
    },
    "relaxed": {
        "rate": "-8%",
        "pitch": "-1Hz",
        "volume": "-3%",
        "description": "Easy-going and unhurried",
    },
    "reassuring": {
        "rate": "-10%",
        "pitch": "-1Hz",
        "volume": "-4%",
        "description": "Gentle and soothing — meant to comfort",
    },

    # ── Serious / Urgent ─────────────────────────────────────────────────────
    "urgent": {
        "rate": "+28%",
        "pitch": "+1Hz",
        "volume": "+12%",
        "description": "Faster and louder — high-stakes or time-critical",
    },
    "serious": {
        "rate": "+5%",
        "pitch": "-1Hz",
        "volume": "+5%",
        "description": "Deliberate, measured, authoritative",
    },
    "focused": {
        "rate": "+8%",
        "pitch": "+0Hz",
        "volume": "+3%",
        "description": "On-task, direct, efficient",
    },
    "alert": {
        "rate": "+22%",
        "pitch": "+2Hz",
        "volume": "+10%",
        "description": "Heightened attention, brisk delivery",
    },

    # ── Apologetic / Empathetic ──────────────────────────────────────────────
    "apologetic": {
        "rate": "-18%",
        "pitch": "-3Hz",
        "volume": "-10%",
        "description": "Slower, softer, lower — remorseful and sincere",
    },
    "empathetic": {
        "rate": "-12%",
        "pitch": "-2Hz",
        "volume": "-7%",
        "description": "Warm, understanding, not rushed",
    },
    "comforting": {
        "rate": "-15%",
        "pitch": "-2Hz",
        "volume": "-8%",
        "description": "Gentle, slower, quiet — offering support",
    },

    # ── Thoughtful / Contemplative ───────────────────────────────────────────
    "thoughtful": {
        "rate": "-8%",
        "pitch": "+0Hz",
        "volume": "-3%",
        "description": "Paced and reflective",
    },
    "curious": {
        "rate": "+5%",
        "pitch": "+2Hz",
        "volume": "+2%",
        "description": "Slightly raised pitch — interested and inquisitive",
    },

    # ── Surprised / Impressed ────────────────────────────────────────────────
    "surprised": {
        "rate": "+20%",
        "pitch": "+5Hz",
        "volume": "+8%",
        "description": "Quick uptick in pitch and pace — genuine surprise",
    },
    "impressed": {
        "rate": "+10%",
        "pitch": "+3Hz",
        "volume": "+4%",
        "description": "Admiring, bright tone",
    },

    # ── Sad / Disappointed ───────────────────────────────────────────────────
    "sad": {
        "rate": "-20%",
        "pitch": "-4Hz",
        "volume": "-12%",
        "description": "Slowest delivery, lowest pitch — somber and subdued",
    },
    "disappointed": {
        "rate": "-15%",
        "pitch": "-3Hz",
        "volume": "-8%",
        "description": "Deflated, slower, quieter",
    },

    # ── Confident / Assertive ────────────────────────────────────────────────
    "confident": {
        "rate": "+15%",
        "pitch": "+1Hz",
        "volume": "+6%",
        "description": "Crisp, direct, and assured",
    },
    "assertive": {
        "rate": "+12%",
        "pitch": "+0Hz",
        "volume": "+8%",
        "description": "Strong, clear delivery",
    },
}

# Canonical set of valid emotion labels for fast O(1) lookup
VALID_EMOTIONS: frozenset[str] = frozenset(EMOTION_PROFILES.keys())

# Aliases: accept alternate spellings the LLM might emit
EMOTION_ALIASES: dict[str, str] = {
    "excited!": "excited",
    "calm.": "calm",
    "urgent!": "urgent",
    "happy!": "happy",
    "sorry": "apologetic",
    "empathy": "empathetic",
    "comfort": "comforting",
    "thinking": "thoughtful",
    "unsure": "curious",
    "surprise": "surprised",
    "flat": "neutral",
    "normal": "neutral",
    "default": "neutral",
}


def get_emotion_profile(emotion: str) -> EmotionProfile:
    """
    Resolve an emotion label to its SSML prosody profile.
    Falls back to 'neutral' for unrecognized/missing labels.
    """
    if not emotion:
        return EMOTION_PROFILES["neutral"]

    label = emotion.strip().lower()
    # Resolve aliases first
    label = EMOTION_ALIASES.get(label, label)
    return EMOTION_PROFILES.get(label, EMOTION_PROFILES["neutral"])
