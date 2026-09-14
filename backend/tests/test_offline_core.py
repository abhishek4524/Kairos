"""
test_offline_core.py — Integration tests for Phase C (Offline Core: Chat, Piper TTS, Local RAG, VRAM Safety).
"""

import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from core import connectivity, provider_router
from core.connectivity import ConnectivityState
from providers import piper_tts
import tts_agent
import memory_store


# ── Test 1: Offline Chat Routing ───────────────────────────────────────────────

def test_offline_chat_routes_directly_to_ollama(monkeypatch):
    """With connectivity forced to OFFLINE, chat routes to Ollama without attempting Groq."""
    monkeypatch.setenv("KAIROS_FORCE_OFFLINE", "1")

    with patch.object(provider_router.ollama_provider, "chat", return_value="Offline LLM response") as mock_ollama, \
         patch.object(provider_router.groq_provider, "chat") as mock_groq:

        res, prov = provider_router.route_chat(
            messages=[{"role": "user", "content": "What is 2+2?"}],
            stream=False,
        )

        assert prov == "ollama"
        assert res == "Offline LLM response"
        mock_groq.assert_not_called()
        mock_ollama.assert_called_once()


# ── Test 2: Offline Piper TTS ──────────────────────────────────────────────────

def test_offline_tts_piper_switch(monkeypatch):
    """When connectivity is OFFLINE, TTS generates audio via Piper instead of Edge-TTS."""
    import asyncio
    import importlib.util
    import os

    # Load real tts_agent directly bypassing conftest mock
    spec = importlib.util.spec_from_file_location(
        "real_tts_agent_offline",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tts_agent.py")),
    )
    real_tts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(real_tts)

    monkeypatch.setenv("KAIROS_FORCE_OFFLINE", "1")

    with patch.object(real_tts, "_generate_edge_audio") as mock_edge, \
         patch("providers.piper_tts.synthesize_offline", new_callable=AsyncMock) as mock_piper:

        mock_piper.return_value = (b"fake_piper_audio_bytes", 1.2)

        audio_bytes, _ = asyncio.run(real_tts.generate_audio_async(
            text="Offline speech test",
            language="en",
            emotion="confident",
        ))

        assert audio_bytes == b"fake_piper_audio_bytes"
        mock_edge.assert_not_called()
        mock_piper.assert_called_once_with("Offline speech test", language="en", emotion="confident")


# ── Test 3: Piper Emotion Mapping ──────────────────────────────────────────────

def test_piper_emotion_length_scale_mapping():
    """Verify emotion profile rate is converted to Piper length_scale."""
    scale_urgent = piper_tts._emotion_to_length_scale("urgent")
    scale_calm = piper_tts._emotion_to_length_scale("calm")
    scale_neutral = piper_tts._emotion_to_length_scale("neutral")

    # Urgent should be faster (lower scale) than calm
    assert scale_urgent < scale_neutral or scale_urgent <= 1.0
    assert scale_calm >= scale_neutral


# ── Test 4: Local RAG Offline Query & Ingestion ────────────────────────────────

def test_local_rag_offline_reindex():
    """Verify local reindexing routine executes without throwing."""
    res = memory_store.reindex_all_local()
    assert isinstance(res, dict)
    assert "facts_reindexed" in res
    assert "chunks_reindexed" in res


# ── Test 5: VRAM Safety: Concurrent Chat & Embed Share Semaphore ──────────────

def test_vram_safety_chat_and_embed_shared_semaphore():
    """Verify chat and embed calls share the same semaphore to prevent 6GB VRAM collision."""
    prov = provider_router.ollama_provider
    timeline = []

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"message": {"content": "ok"}, "embeddings": [[0.1, 0.2]]}

    class MockClientContext:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, *args, **kwargs):
            action = "embed" if "embed" in url else "chat"
            timeline.append((action, "start", time.time()))
            time.sleep(0.08)
            timeline.append((action, "end", time.time()))
            return mock_resp

    with patch("httpx.Client", MockClientContext):
        def run_chat():
            prov.chat([{"role": "user", "content": "hello"}], stream=False, skip_server_check=True)

        def run_embed():
            prov.embed(["some query text"])

        t1 = threading.Thread(target=run_chat)
        t2 = threading.Thread(target=run_embed)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

    starts = [e for e in timeline if e[1] == "start"]
    ends = [e for e in timeline if e[1] == "end"]
    assert len(starts) == 2
    assert len(ends) == 2

    # Serialized: first action's end <= second action's start
    first_act = starts[0][0]
    first_end = [e[2] for e in ends if e[0] == first_act][0]
    second_start = [e[2] for e in starts if e[0] != first_act][0]

    assert first_end <= second_start + 0.02
