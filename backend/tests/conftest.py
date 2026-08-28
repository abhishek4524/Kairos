"""
conftest.py — Pytest fixtures for Kairos backend test suite.

Strategy: inject mock modules into sys.modules BEFORE any backend module is imported.
This bypasses all heavy-init side effects (Redis ping, Groq client, Whisper model loading,
sentence-transformers download, ChromaDB init) so the test suite runs in seconds.
"""

import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock

# ── Ensure backend root is on sys.path ─────────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ── Set test environment variables BEFORE any import ──────────────────────────
os.environ.setdefault("GROQ_API_KEY", "mock_groq_api_key_for_testing")
os.environ.setdefault("NVIDIA_API_KEY", "mock_nvidia_api_key_for_testing")
os.environ.setdefault("KAIROS_SECURITY_MODE", "strict")
os.environ.setdefault("ADMIN_PASSWORD", "testadmin123")
os.environ.setdefault("STT_MODE", "api")

# ── Mock heavy / network-dependent modules ─────────────────────────────────────
# These must be injected BEFORE main.py (and its imports) are evaluated.

# 1. faster_whisper
sys.modules.setdefault("faster_whisper", MagicMock())

# 2. silero_vad
sys.modules.setdefault("silero_vad", MagicMock())

# 3. sentence_transformers (used by memory_store / chromadb embedding function)
_mock_st = MagicMock()
_mock_embed_model = MagicMock()
_mock_embed_model.encode.return_value = [[0.1] * 384]
_mock_st.SentenceTransformer.return_value = _mock_embed_model
sys.modules.setdefault("sentence_transformers", _mock_st)

# 4. redis — mock the Redis client so llm_agent.py doesn't block on ping()
_mock_redis_mod = MagicMock()
_mock_redis_inst = MagicMock()
_mock_redis_inst.ping.return_value = True
_mock_redis_inst.get.return_value = None
_mock_redis_inst.set.return_value = True
_mock_redis_inst.scan_iter.return_value = iter([])
_mock_redis_mod.Redis.return_value = _mock_redis_inst
sys.modules.setdefault("redis", _mock_redis_mod)

# 5. groq — mock Groq client so llm_agent.py doesn't need a real API key
_mock_groq_mod = MagicMock()
_mock_groq_client = MagicMock()
_mock_groq_mod.Groq.return_value = _mock_groq_client
sys.modules.setdefault("groq", _mock_groq_mod)

# 6. openai — mock OpenAI client so nvidia nim fallback doesn't fail
_mock_openai_mod = MagicMock()
_mock_openai_mod.OpenAI.return_value = MagicMock()
sys.modules.setdefault("openai", _mock_openai_mod)

# 7. chromadb — mock to avoid ChromaDB's own startup/download
_mock_chromadb = MagicMock()
_mock_collection = MagicMock()
_mock_collection.query.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
_mock_collection.add.return_value = None
_mock_collection.get.return_value = {"ids": [], "documents": [], "metadatas": []}
_mock_client = MagicMock()
_mock_client.get_or_create_collection.return_value = _mock_collection
_mock_chromadb.PersistentClient.return_value = _mock_client
sys.modules.setdefault("chromadb", _mock_chromadb)
sys.modules.setdefault("chromadb.config", MagicMock())
sys.modules.setdefault("chromadb.utils", MagicMock())
sys.modules.setdefault("chromadb.utils.embedding_functions", MagicMock())

# 8. transcriber — inject full mock module so `from transcriber import RealTimeTranscriber` works
_mock_transcriber_instance = MagicMock()
_mock_transcriber_instance.process_audio_chunk.return_value = None
_mock_transcriber_instance.set_sensitivity = MagicMock()
_mock_transcriber_mod = MagicMock()
_mock_transcriber_mod.RealTimeTranscriber.return_value = _mock_transcriber_instance
sys.modules["transcriber"] = _mock_transcriber_mod

# 9. edge_tts / tts_agent — mock TTS to avoid edge-tts network calls
_mock_edge_tts = MagicMock()
sys.modules.setdefault("edge_tts", _mock_edge_tts)
_mock_tts_agent = MagicMock()
_mock_tts_agent.generate_audio_async = AsyncMock(return_value=(b"fake_audio", 1.0))
sys.modules.setdefault("tts_agent", _mock_tts_agent)

# 10. pydub (optional audio processing dep)
sys.modules.setdefault("pydub", MagicMock())
sys.modules.setdefault("pydub.audio_segment", MagicMock())
sys.modules.setdefault("webrtcvad", MagicMock())

# ── Now import main (it will use all mocked modules above) ─────────────────────
import pytest
from fastapi.testclient import TestClient
import main

# Replace the module-level transcriber instance that main.py already set
main.transcriber = _mock_transcriber_instance
# Replace TTS used by main
main.generate_audio_async = AsyncMock(return_value=(b"fake_audio", 1.0))


@pytest.fixture(scope="session")
def client():
    """FastAPI TestClient fixture (session-scoped for speed)."""
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def mock_browser():
    """Mocks all browser automation calls to prevent real browser launches."""
    with patch("agent_tools.browser.navigate_to") as mock_nav, \
         patch("agent_tools.browser.find_and_click") as mock_click, \
         patch("agent_tools.browser.type_into") as mock_type, \
         patch("agent_tools.browser.scroll_page") as mock_scroll, \
         patch("agent_tools.browser.extract_page_text") as mock_extract, \
         patch("agent_tools.browser.go_back") as mock_back, \
         patch("agent_tools.browser.open_new_tab") as mock_new_tab, \
         patch("agent_tools.browser.switch_tab") as mock_switch, \
         patch("agent_tools.browser.youtube_play_video") as mock_yt_play, \
         patch("agent_tools.browser.youtube_control") as mock_yt_ctrl:

        mock_nav.return_value       = {"success": True, "message": "Navigated", "url": "https://example.com"}
        mock_click.return_value     = {"success": True, "message": "Clicked", "confirmation": {"action": "clicked"}}
        mock_type.return_value      = {"success": True, "message": "Typed", "confirmation": {"action": "typed"}}
        mock_scroll.return_value    = {"success": True, "message": "Scrolled"}
        mock_extract.return_value   = {"success": True, "title": "Example", "url": "https://example.com", "text_content": "Page content"}
        mock_back.return_value      = {"success": True, "message": "Navigated back"}
        mock_new_tab.return_value   = {"success": True, "message": "Opened new tab"}
        mock_switch.return_value    = {"success": True, "message": "Switched tab"}
        mock_yt_play.return_value   = {"success": True, "message": "Playing video #1"}
        mock_yt_ctrl.return_value   = {"success": True, "message": "YouTube control done"}

        yield {
            "navigate_to": mock_nav,
            "find_and_click": mock_click,
            "type_into": mock_type,
            "scroll_page": mock_scroll,
            "extract_page_text": mock_extract,
            "go_back": mock_back,
            "open_new_tab": mock_new_tab,
            "switch_tab": mock_switch,
            "youtube_play_video": mock_yt_play,
            "youtube_control": mock_yt_ctrl,
        }
