"""
elevenlabs_tts.py — ElevenLabs TTS provider for Arya.

Calls the ElevenLabs REST API to synthesize speech.
Returns raw MP3 bytes.

Configured via:
  ELEVENLABS_API_KEY  — required
  ELEVENLABS_VOICE_ID — optional, defaults to Shanaya (soft youthful Hinglish female)
                        Free-tier fallback: Rachel "21m00Tcm4TlvDq8ikWAM"
                        Other options:
                          "wViXBPUzp2ZZixB1xQuM"  — Saavi (soothing Hindi)
                          "EXAVITQu4vr4xnSDxMaL"  — Bella
"""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("arya.elevenlabs_tts")

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"
_DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"       # Rachel — Premade Free Female Voice (100% free tier compatible)
_PREMADE_FREE_FALLBACK_VOICE = "21m00Tcm4TlvDq8ikWAM"  # Rachel


def _get_config() -> tuple[str, str]:
    """Returns (api_key, voice_id). Strips comments and trailing spaces."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    raw_vid = os.environ.get("ELEVENLABS_VOICE_ID", "").split("#")[0].strip()
    voice_id = raw_vid or _DEFAULT_VOICE_ID
    return api_key, voice_id


def is_configured() -> bool:
    api_key, _ = _get_config()
    return bool(api_key)


async def synthesize(
    text: str,
    voice_id: Optional[str] = None,
    language: str = "en",
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.0,
    use_speaker_boost: bool = True,
) -> bytes:
    """
    Synthesize text to speech using ElevenLabs REST API.
    Returns raw MP3 bytes.
    """
    api_key, default_voice = _get_config()
    if not api_key:
        raise RuntimeError("ElevenLabs TTS: ELEVENLABS_API_KEY is not set")

    vid = (voice_id or default_voice).split("#")[0].strip()
    url = f"{ELEVENLABS_API_BASE}/text-to-speech/{vid}"

    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.50,
            "similarity_boost": 0.75,
            "style": 0.1,
            "use_speaker_boost": use_speaker_boost,
        },
    }

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code == 402 and vid != _PREMADE_FREE_FALLBACK_VOICE:
            logger.warning("[ElevenLabs TTS] Custom voice %s requires paid plan (402). Retrying with premade free female voice %s...", vid, _PREMADE_FREE_FALLBACK_VOICE)
            retry_url = f"{ELEVENLABS_API_BASE}/text-to-speech/{_PREMADE_FREE_FALLBACK_VOICE}"
            resp = await client.post(retry_url, json=payload, headers=headers)

        if resp.status_code != 200:
            raise RuntimeError(
                f"ElevenLabs TTS API error {resp.status_code}: {resp.text[:300]}"
            )
        audio_bytes = resp.content

    if not audio_bytes:
        raise RuntimeError("ElevenLabs TTS returned empty audio bytes")

    logger.info("[ElevenLabs TTS] Synthesized %d chars → %d bytes MP3 (voice=%s)", len(text), len(audio_bytes), vid)
    return audio_bytes

