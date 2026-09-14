"""
test_providers_and_router.py — Unit tests for Phase A (Provider Abstraction Layer & Router).
"""

import json
import threading
import time
from unittest.mock import MagicMock, patch
import pytest

from providers.base_provider import ProviderHealth
from providers.groq_provider import GroqProvider
from providers.nvidia_provider import NvidiaProvider
from providers.ollama_provider import OllamaProvider, get_shared_semaphore
from core import provider_router


# ── Test Groq Provider ─────────────────────────────────────────────────────────

def test_groq_provider_chat_streaming():
    provider = GroqProvider(api_key="fake_key")
    mock_client = MagicMock()
    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [MagicMock(delta=MagicMock(content="Hello "))]
    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [MagicMock(delta=MagicMock(content="Abhishek!"))]
    mock_client.chat.completions.create.return_value = [mock_chunk1, mock_chunk2]

    provider._client = mock_client
    gen = provider.chat([{"role": "user", "content": "hi"}], stream=True)
    chunks = list(gen)
    assert chunks == ["Hello ", "Abhishek!"]


def test_groq_provider_health_check_pass():
    provider = GroqProvider(api_key="fake_key")
    mock_client = MagicMock()
    provider._client = mock_client
    health = provider.health_check()
    assert health.available is True
    assert health.provider_name == "groq"


def test_groq_provider_health_check_fail():
    provider = GroqProvider(api_key="fake_key")
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("Groq 429 Rate Limit")
    provider._client = mock_client
    health = provider.health_check()
    assert health.available is False
    assert "Rate Limit" in health.error


# ── Test NVIDIA NIM Provider ──────────────────────────────────────────────────

def test_nvidia_provider_chat_non_streaming():
    provider = NvidiaProvider(api_key="fake_key")
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="NVIDIA response"))]
    mock_client.chat.completions.create.return_value = mock_resp
    provider._client = mock_client

    res = provider.chat([{"role": "user", "content": "hello"}], stream=False)
    assert res == "NVIDIA response"


def test_nvidia_provider_health_check():
    provider = NvidiaProvider(api_key="fake_key")
    mock_client = MagicMock()
    provider._client = mock_client
    health = provider.health_check()
    assert health.available is True
    assert health.provider_name == "nvidia"


# ── Test Ollama Provider ──────────────────────────────────────────────────────

def test_ollama_provider_model_selection_and_options():
    provider = OllamaProvider(
        base_url="http://127.0.0.1:11434",
        general_model="qwen2.5:7b",
        coder_model="qwen2.5-coder:7b",
        num_ctx=4096,
        keep_alive="15m",
    )

    # General intent -> qwen2.5:7b
    assert provider.select_model_for_intent("chitchat") == "qwen2.5:7b"
    # Coding intent -> qwen2.5-coder:7b
    assert provider.select_model_for_intent("coding") == "qwen2.5-coder:7b"
    assert provider.select_model_for_intent("terminal") == "qwen2.5-coder:7b"

    # Test payload generation with mocked httpx
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {"message": {"content": "Local code generated"}}
        mock_client.post.return_value = mock_resp

        res = provider.chat(
            messages=[{"role": "user", "content": "write python"}],
            stream=False,
            intent_category="coding",
            skip_server_check=True,
        )
        assert res == "Local code generated"

        # Check payload
        call_args = mock_client.post.call_args
        assert call_args is not None
        payload = call_args[1]["json"]
        assert payload["model"] == "qwen2.5-coder:7b"
        assert payload["keep_alive"] == "15m"
        assert payload["options"]["num_ctx"] == 4096


def test_ollama_provider_structured_health_check():
    provider = OllamaProvider(
        general_model="qwen2.5:7b",
        coder_model="qwen2.5-coder:7b",
        embed_model="nomic-embed-text",
    )

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        # Scenario 1: All models present
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "models": [
                {"name": "qwen2.5:7b"},
                {"name": "qwen2.5-coder:7b"},
                {"name": "nomic-embed-text:latest"},
            ]
        }
        mock_client.get.return_value = mock_resp

        h1 = provider.health_check()
        assert h1.available is True
        assert h1.models_status["qwen2.5:7b"] is True
        assert h1.models_status["qwen2.5-coder:7b"] is True
        assert h1.models_status["nomic-embed-text"] is True
        assert h1.error is None

        # Scenario 2: Ollama running but missing coder model
        mock_resp2 = MagicMock(status_code=200)
        mock_resp2.json.return_value = {
            "models": [
                {"name": "qwen2.5:7b"},
                {"name": "nomic-embed-text:latest"},
            ]
        }
        mock_client.get.return_value = mock_resp2

        h2 = provider.health_check()
        assert h2.available is False
        assert h2.models_status["qwen2.5-coder:7b"] is False
        assert "missing model" in h2.error.lower()

        # Scenario 3: Ollama server completely down
        mock_client.get.side_effect = Exception("Connection refused")
        h3 = provider.health_check()
        assert h3.available is False
        assert "unreachable" in h3.error.lower()


def test_ollama_max_parallel_semaphore_serialization():
    """Verify max_parallel=1 semaphore enforces serial execution of concurrent Ollama calls."""
    provider = OllamaProvider()
    execution_timeline = []

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"message": {"content": "res"}}

    class MockClientContext:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, *args, **kwargs):
            payload = kwargs.get("json", {})
            idx = payload.get("messages", [{}])[0].get("content", "")
            execution_timeline.append((idx, "start", time.time()))
            time.sleep(0.08)
            execution_timeline.append((idx, "end", time.time()))
            return mock_resp

    with patch("httpx.Client", MockClientContext):
        def fake_chat(idx: int):
            provider.chat([{"role": "user", "content": f"msg_{idx}"}], stream=False, skip_server_check=True)

        t1 = threading.Thread(target=fake_chat, args=(1,))
        t2 = threading.Thread(target=fake_chat, args=(2,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

    # Assert non-overlapping intervals: first call's end must be <= second call's start
    starts = [e for e in execution_timeline if e[1] == "start"]
    ends = [e for e in execution_timeline if e[1] == "end"]
    assert len(starts) == 2
    assert len(ends) == 2

    # The one that started first must finish before the second one starts
    first_task = starts[0][0]
    first_end = [e[2] for e in ends if e[0] == first_task][0]
    second_start = [e[2] for e in starts if e[0] != first_task][0]

    assert first_end <= second_start + 0.02


# ── Test Provider Router Fallback Sequence ────────────────────────────────────

def test_router_groq_primary_success():
    # Upstream providers fail; Groq succeeds
    with patch.object(provider_router.gemini_provider, "chat", side_effect=Exception("Gemini N/A")), \
         patch.object(provider_router.openrouter_provider, "chat", side_effect=Exception("OR N/A")), \
         patch.object(provider_router.groq_provider, "chat", return_value="Groq answer"):
        res, provider = provider_router.route_chat(
            messages=[{"role": "user", "content": "hi"}],
            stream=False,
        )
        assert provider == "groq"
        assert res == "Groq answer"


def test_router_falls_through_groq_to_nvidia():
    with patch.object(provider_router.gemini_provider, "chat", side_effect=Exception("Gemini N/A")), \
         patch.object(provider_router.openrouter_provider, "chat", side_effect=Exception("OR N/A")), \
         patch.object(provider_router.groq_provider, "chat", side_effect=Exception("Groq 500")), \
         patch.object(provider_router.nvidia_provider, "chat", return_value="NVIDIA answer"):
        res, provider = provider_router.route_chat(
            messages=[{"role": "user", "content": "hi"}],
            stream=False,
        )
        assert provider == "nvidia"
        assert res == "NVIDIA answer"


def test_router_falls_through_to_ollama_on_all_cloud_failures():
    with patch.object(provider_router.gemini_provider, "chat", side_effect=Exception("Gemini N/A")), \
         patch.object(provider_router.openrouter_provider, "chat", side_effect=Exception("OR N/A")), \
         patch.object(provider_router.groq_provider, "chat", side_effect=Exception("Groq Timeout")), \
         patch.object(provider_router.nvidia_provider, "chat", side_effect=Exception("NVIDIA 401")), \
         patch.object(provider_router.mistral_provider, "chat", side_effect=Exception("Mistral N/A")), \
         patch.object(provider_router.ollama_provider, "chat", return_value="Ollama local answer"):
        res, provider = provider_router.route_chat(
            messages=[{"role": "user", "content": "hi"}],
            stream=False,
        )
        assert provider == "ollama"
        assert res == "Ollama local answer"


def test_router_direct_ollama_when_offline_forced(monkeypatch):
    monkeypatch.setenv("KAIROS_FORCE_OFFLINE", "1")
    with patch.object(provider_router.ollama_provider, "chat", return_value="Direct local answer"), \
         patch.object(provider_router.groq_provider, "chat") as mock_groq:
        res, provider = provider_router.route_chat(
            messages=[{"role": "user", "content": "hi"}],
            stream=False,
        )
        assert provider == "ollama"
        assert res == "Direct local answer"
        mock_groq.assert_not_called()
