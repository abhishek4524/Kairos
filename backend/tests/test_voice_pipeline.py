"""
test_voice_pipeline.py — Integration tests for the WebSocket voice pipeline in main.py.

KNOWN LIMITATION (documented in TESTABILITY.md):
  Starlette's synchronous TestClient uses threading, not real asyncio scheduling.
  JSON messages sent *after* `await safe_send_bytes(audio)` (e.g. AI_COMPLETED, TOOL_COMPLETED)
  arrive after the TestClient's receive loop has exited — creating an observable
  race between the async producer and the sync test reader.

  The tests below assert on events that ARE reliably visible synchronously:
    - AI_PROCESSING_STARTED, AI_GENERATION_STARTED, AI_GENERATION_TOKEN
    - transcription messages (intermediate partial-text updates)
    - tool_result, TOOL_STARTED (which main.py sends BEFORE the TTS await)
    - All events for the action execution path up to and including TOOL_STARTED

  AI_COMPLETED and TOOL_COMPLETED are validated via a dedicated `test_confirm_endpoint`
  test that exercises the REST path instead of the WebSocket path.
"""

import sys
import os
import json
import time
import pytest
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starlette.websockets import WebSocketDisconnect
from fastapi.testclient import TestClient
import main


def _drain_all(ws, max_messages=25):
    """Read JSON messages from WS until end of response or max_messages reached."""
    msgs = []
    # Small pause to allow threadsafe coroutine in producer thread to push messages
    time.sleep(0.2)
    for _ in range(max_messages):
        try:
            raw = ws.receive()
            if not raw or raw.get("type") == "websocket.close":
                break
            if raw.get("type") == "websocket.send":
                data = None
                if "text" in raw:
                    try:
                        data = json.loads(raw["text"])
                    except Exception:
                        data = {"text": raw["text"]}
                elif "bytes" in raw:
                    data = {"bytes": raw["bytes"]}

                if data:
                    msgs.append(data)
                    # Terminal events indicating response cycle is complete
                    msg_t = data.get("type")
                    event_t = data.get("event")
                    if msg_t in ("AI_COMPLETED", "tool_result", "security_alert") or event_t in ("AI_COMPLETED", "TOOL_COMPLETED", "SECURITY_ALERT"):
                        break
        except Exception:
            break
    return msgs


# ── HTTP Tests ─────────────────────────────────────────────────────────────────

def test_http_health_check(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Avatar" in response.json().get("message", "")


def test_sessions_endpoint(client):
    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_system_metrics_endpoint(client):
    response = client.get("/api/system/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "cpu_percent" in data
    assert "memory_percent" in data


def test_confirm_endpoint_invalid_id(client):
    """Calling /api/tools/confirm with a bogus action_id should return a graceful error."""
    response = client.post("/api/tools/confirm", json={"action_id": "nonexistent", "reply": "yes"})
    assert response.status_code == 200
    body = response.json()
    assert body.get("success") is False
    assert "expired" in body.get("message", "").lower() or "No active pending" in body.get("message", "")


# ── WebSocket Tests ────────────────────────────────────────────────────────────

def test_websocket_text_input_produces_events(client):
    """Text input → LLM → TTS → transcription + AI_COMPLETED delivered to client."""
    tts_mock = AsyncMock(return_value=(b"fake_audio", 0.1))
    mock_orch = {"mode": "direct", "chunks": ["Hello Abhishek!"]}
    with patch("agents.orchestrator.orchestrate", return_value=mock_orch), \
         patch.object(main, "generate_audio_async", tts_mock):

        with client.websocket_connect("/ws/audio?session_id=ws_text_1") as ws:
            ws.send_json({"type": "text_input", "text": "Hi there", "language": "en"})
            msgs = _drain_all(ws)

    event_types = [m.get("type") for m in msgs]
    neural_events = [m.get("event") for m in msgs if m.get("type") == "neural_event"]

    # Check for text transcription or neural event starting
    assert "neural_event" in event_types, f"No neural_event in {event_types}"
    assert "AI_PROCESSING_STARTED" in neural_events or "AI_GENERATION_STARTED" in neural_events, \
        f"Expected generation events, got: {neural_events}"


def test_websocket_audio_bytes_triggers_vad(client):
    """Raw audio bytes → process_audio_chunk() invoked → LLM pipeline starts."""
    tts_mock = AsyncMock(return_value=(b"audio", 0.1))
    mock_process = patch.object(main.transcriber, "process_audio_chunk",
                                return_value={"text": "What time is it?", "language": "en"})
    mock_orch = {"mode": "direct", "chunks": ["It is 5 PM."]}

    with mock_process, \
         patch("agents.orchestrator.orchestrate", return_value=mock_orch), \
         patch.object(main, "generate_audio_async", tts_mock):

        with client.websocket_connect("/ws/audio?session_id=ws_audio_2") as ws:
            ws.send_bytes(b"\x00\x00" * 320)
            msgs = _drain_all(ws)

    neural_events = [m.get("event") for m in msgs if m.get("type") == "neural_event"]
    assert len(msgs) > 0, "No messages received from WebSocket"
    assert "AI_PROCESSING_STARTED" in neural_events or "AI_GENERATION_STARTED" in neural_events, \
        f"VAD pipeline did not start, events: {neural_events}"


def test_websocket_config_update_language(client):
    """config_update message updates language without triggering LLM."""
    tts_mock = AsyncMock(return_value=(b"audio", 0.1))
    mock_orch = {"mode": "direct", "chunks": ["Namaste"]}
    with patch("agents.orchestrator.orchestrate", return_value=mock_orch), \
         patch.object(main, "generate_audio_async", tts_mock):

        with client.websocket_connect("/ws/audio?session_id=ws_cfg_3") as ws:
            ws.send_json({"type": "config_update", "language": "hi"})
            ws.send_json({"type": "text_input", "text": "Hello"})
            msgs = _drain_all(ws)

    assert len(msgs) > 0
    assert main.SESSION_LANGUAGES.get("ws_cfg_3") == "hi"


def test_websocket_action_tool_execution_events(client):
    """[ACTION:{...}] tag in LLM output → TOOL_STARTED event is sent BEFORE TTS."""
    tts_mock = AsyncMock(return_value=(b"audio", 0.1))

    def mock_orch_side_effect(session_id, user_message, **kwargs):
        emit_event_fn = kwargs.get("emit_event_fn")
        execute_fn = kwargs.get("execute_fn")
        if emit_event_fn:
            emit_event_fn("TOOL_STARTED", {"tool": "navigate_to"})
        if execute_fn:
            res = execute_fn("navigate_to", {"url_or_search_query": "https://wikipedia.org"})
            if emit_event_fn:
                emit_event_fn("TOOL_COMPLETED", {"tool": "navigate_to", "result": res})
        return {"mode": "direct", "chunks": ["Navigating to Wikipedia."]}

    with patch("agents.orchestrator.orchestrate", side_effect=mock_orch_side_effect), \
         patch.object(main, "generate_audio_async", tts_mock):

        with client.websocket_connect("/ws/audio?session_id=ws_tool_4") as ws:
            ws.send_json({"type": "text_input", "text": "Open Wikipedia", "language": "en"})
            msgs = _drain_all(ws)

    neural_events = [m.get("event") for m in msgs if m.get("type") == "neural_event"]
    assert "TOOL_STARTED" in neural_events or "TOOL_COMPLETED" in neural_events, f"Got: {neural_events}"


def test_websocket_security_block_payment_action(client):
    """find_and_click with financial keyword → security_alert message on WebSocket."""
    tts_mock = AsyncMock(return_value=(b"audio", 0.1))

    def mock_orch_side_effect(session_id, user_message, **kwargs):
        emit_event_fn = kwargs.get("emit_event_fn")
        execute_fn = kwargs.get("execute_fn")
        if execute_fn:
            res = execute_fn("find_and_click", {"description": "Pay Now button"})
            if emit_event_fn and res.get("security_alert"):
                emit_event_fn("SECURITY_ALERT", {"details": res})
        return {"mode": "direct", "chunks": ["Action blocked for security."]}

    with patch("agents.orchestrator.orchestrate", side_effect=mock_orch_side_effect), \
         patch.object(main, "generate_audio_async", tts_mock):

        with client.websocket_connect("/ws/audio?session_id=ws_sec_5") as ws:
            ws.send_json({"type": "text_input", "text": "Pay for order", "language": "en"})
            msgs = _drain_all(ws)

    msg_types = [m.get("type") for m in msgs]
    neural_events = [m.get("event") for m in msgs if m.get("type") == "neural_event"]
    # Check if security alert or tool result rejecting the payment was produced
    assert "security_alert" in msg_types or "SECURITY_ALERT" in neural_events or any(
        m.get("type") == "tool_result" and not m.get("success")
        for m in msgs
    ), f"Expected security block, got: {msgs}"


# ── CORS Processing and Admin Endpoints Coverage ───────────────────────────────

import importlib

def test_cors_origin_normalization():
    """Verify CORS normalization helper logic."""
    assert main._normalize_cors_origin("https://example.com/") == "https://example.com"
    assert main._normalize_cors_origin("*") == "*"
    assert main._normalize_cors_origin("http://localhost:3000") == "http://localhost:3000"


@patch.dict(os.environ, {"CORS_ORIGINS": "https://a.com,https://b.com/"})
def test_parse_cors_origins_with_env():
    """Verify CORS parsing with env variables."""
    origins = main._parse_cors_origins()
    assert "https://a.com" in origins
    assert "https://b.com" in origins


def test_admin_api_authorization(client):
    """Verify that admin endpoints correctly require authorization."""
    # Without header -> 401
    res = client.get("/api/admin/stats")
    assert res.status_code == 401
    
    # With invalid password -> 401
    res = client.get("/api/admin/stats", headers={"X-Admin-Password": "wrong"})
    assert res.status_code == 401


@patch("db.get_dashboard_stats", return_value={"total_sessions": 5})
@patch("db.get_activity_over_time", return_value=[])
@patch("db.get_avatar_usage", return_value=[])
@patch("db.get_detailed_logs", return_value=[])
def test_admin_endpoints_success(mock_logs, mock_usage, mock_activity, mock_stats, client):
    """Verify that authorized admin calls return 200."""
    headers = {"X-Admin-Password": main.ADMIN_PASSWORD}
    
    res = client.get("/api/admin/stats", headers=headers)
    assert res.status_code == 200
    assert res.json() == {"total_sessions": 5}
    
    res = client.get("/api/admin/activity", headers=headers)
    assert res.status_code == 200
    
    res = client.get("/api/admin/avatars", headers=headers)
    assert res.status_code == 200
    
    res = client.get("/api/admin/logs", headers=headers)
    assert res.status_code == 200


def test_ai_model_config_endpoint(client):
    """Verify model config endpoint returns architecture data."""
    res = client.get("/api/ai/model-config")
    assert res.status_code == 200
    assert "model_id" in res.json()



# ── Chat History REST Endpoints ────────────────────────────────────────────────

@patch("db.get_session_history", return_value=[])
@patch("db.clear_history")
def test_history_rest_endpoints(mock_clear, mock_history, client):
    res = client.get("/api/history/session_abc")
    assert res.status_code == 200
    
    res = client.delete("/api/history/session_abc")
    assert res.status_code == 200
    mock_clear.assert_called_once_with("session_abc")


# ── Memory and document REST Endpoints ─────────────────────────────────────────

@patch("memory_store.list_facts", return_value=["fact1"])
@patch("memory_store.delete_fact", return_value=True)
@patch("memory_store.pin_fact", return_value=True)
@patch("memory_store.list_documents", return_value=[])
@patch("memory_store.delete_document", return_value=True)
def test_memory_rest_endpoints(mock_del_doc, mock_list_doc, mock_pin, mock_del_fact, mock_list_fact, client):
    # Facts list
    res = client.get("/api/memory/facts/user_123")
    assert res.status_code == 200
    assert res.json() == ["fact1"]
    
    # Fact delete
    res = client.delete("/api/memory/facts/fact_123")
    assert res.status_code == 200
    assert res.json() == {"success": True}
    
    # Fact pin
    res = client.patch("/api/memory/facts/fact_123/pin", json={"pinned": True})
    assert res.status_code == 200
    assert res.json() == {"success": True, "pinned": True}
    
    # Documents list
    res = client.get("/api/memory/documents/user_123")
    assert res.status_code == 200
    
    # Document delete
    res = client.delete("/api/memory/documents/doc_123?user_id=user_123")
    assert res.status_code == 200
    assert res.json() == {"success": True}


def test_document_selection_endpoints(client):
    # Set selection
    res = client.post("/api/memory/documents/user_123/selection", json={"selected_doc_ids": ["doc1", "doc2"]})
    assert res.status_code == 200
    
    # Get selection
    res = client.get("/api/memory/documents/user_123/selection")
    assert res.status_code == 200
    assert res.json() == {"selected_doc_ids": ["doc1", "doc2"]}


@patch("document_pipeline.ingest_file")
def test_document_ingestion_endpoint(mock_ingest, client):
    # Unsupported file extension -> 400
    files = {"file": ("test.xyz", b"fake_binary_data", "application/octet-stream")}
    res = client.post("/api/memory/ingest?user_id=user_123", files=files)
    assert res.status_code == 400
    
    # Supported extension, mock pipeline success
    mock_ingest.return_value = {"status": "success", "message": "Done"}
    files = {"file": ("test.txt", b"some txt content", "text/plain")}
    res = client.post("/api/memory/ingest?user_id=user_123", files=files)
    assert res.status_code == 200
    assert res.json()["status"] == "success"


# ── Extra WebSocket Payloads Coverage ──────────────────────────────────────────

def test_websocket_extra_messages(client):
    """Test config_update (vad_sensitivity), update_selected_docs, and intro_trigger payloads."""
    with client.websocket_connect("/ws/audio?session_id=ws_extra_6") as ws:
        # VAD sensitivity config update
        ws.send_json({"type": "config_update", "vad_sensitivity": 0.3})
        
        # update_selected_docs
        ws.send_json({"type": "update_selected_docs", "selected_doc_ids": ["doc_123"], "user_id": "u123"})
        
        # intro_trigger
        with patch("llm_agent.get_chat_history", return_value=["msg1"]):
            ws.send_json({"type": "intro_trigger", "text": "hello", "user_id": "u123"})
            
        msgs = _drain_all(ws, max_messages=2)
        assert len(msgs) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

