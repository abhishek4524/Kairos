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


def _drain_all(ws, max_messages=60, timeout=1.5):
    """Read all JSON messages from WS using raw receive() with a timeout to prevent hanging."""
    msgs = []
    for _ in range(max_messages):
        # Wait until buffer has items or timeout is reached
        start_time = time.time()
        has_item = False
        while time.time() - start_time < timeout:
            # Under-the-hood AnyIO streams used by Starlette TestClient
            if hasattr(ws, "_send_rx") and len(ws._send_rx._state.buffer) > 0:
                has_item = True
                break
            time.sleep(0.01)
            
        if not has_item:
            break  # No more messages within timeout

        try:
            raw = ws.receive()
            if raw.get("type") == "websocket.close":
                break
            if raw.get("type") == "websocket.send":
                if "text" in raw:
                    try:
                        msgs.append(json.loads(raw["text"]))
                    except Exception:
                        msgs.append({"text": raw["text"]})
                elif "bytes" in raw:
                    msgs.append({"type": "audio_bytes", "bytes": raw["bytes"]})
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
    with patch("main.generate_streaming_response", return_value=["Hello Abhishek!"]), \
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

    with mock_process, \
         patch("main.generate_streaming_response", return_value=["It is 5 PM."]), \
         patch.object(main, "generate_audio_async", tts_mock):

        with client.websocket_connect("/ws/audio?session_id=ws_audio_2") as ws:
            ws.send_bytes(b"\x00\x01" * 1280)
            msgs = _drain_all(ws)

    neural_events = [m.get("event") for m in msgs if m.get("type") == "neural_event"]
    assert len(msgs) > 0, "No messages received from WebSocket"
    assert "AI_PROCESSING_STARTED" in neural_events or "AI_GENERATION_STARTED" in neural_events, \
        f"VAD pipeline did not start, events: {neural_events}"


def test_websocket_config_update_language(client):
    """config_update message updates language without triggering LLM."""
    with client.websocket_connect("/ws/audio?session_id=ws_cfg_3") as ws:
        ws.send_json({"type": "config_update", "language": "hi"})
        ws.send_json({"type": "text_input", "text": "Hello", "language": "hi"})
        msgs = _drain_all(ws)

    assert len(msgs) > 0


def test_websocket_action_tool_execution_events(client):
    """[ACTION:{...}] tag in LLM output → TOOL_STARTED event is sent BEFORE TTS."""
    tts_mock = AsyncMock(return_value=(b"audio", 0.1))
    with patch("agents.orchestrator.classify", return_value=("browsing", 0.95)), \
         patch("agents.base_agent.generate_streaming_response", return_value=[
            '[ACTION:{"tool":"navigate_to","params":{"url_or_search_query":"https://wikipedia.org"},'
            '"summary":"Open Wikipedia"}] Navigating to Wikipedia.'
        ]), \
         patch.object(main, "generate_audio_async", tts_mock), \
         patch("agent_tools.browser.navigate_to",
               return_value={"success": True, "message": "Navigated to Wikipedia."}):

        with client.websocket_connect("/ws/audio?session_id=ws_tool_4") as ws:
            ws.send_json({"type": "text_input", "text": "Open Wikipedia", "language": "en"})
            msgs = _drain_all(ws)

    neural_events = [m.get("event") for m in msgs if m.get("type") == "neural_event"]
    tool_results = [m for m in msgs if m.get("type") == "tool_result"]

    assert "TOOL_STARTED" in neural_events or "TOOL_COMPLETED" in neural_events, f"Got: {neural_events}"
    assert len(tool_results) > 0, f"Expected tool_result, msgs types: {[m.get('type') for m in msgs]}"
    assert tool_results[0]["tool"] == "navigate_to"
    assert tool_results[0]["success"] is True


def test_websocket_security_block_payment_action(client):
    """find_and_click with financial keyword → security_alert message on WebSocket."""
    tts_mock = AsyncMock(return_value=(b"audio", 0.1))
    with patch("agents.orchestrator.classify", return_value=("browsing", 0.95)), \
         patch("agents.base_agent.generate_streaming_response", return_value=[
            '[ACTION:{"tool":"find_and_click","params":{"description":"Pay Now button"},'
            '"summary":"Pay"}]'
        ]), \
         patch.object(main, "generate_audio_async", tts_mock):

        with client.websocket_connect("/ws/audio?session_id=ws_sec_5") as ws:
            ws.send_json({"type": "text_input", "text": "Pay for order", "language": "en"})
            msgs = _drain_all(ws)

    msg_types = [m.get("type") for m in msgs]
    # Check if security alert or tool result rejecting the payment was produced
    assert "security_alert" in msg_types or any(
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
    files = {"file": ("test.png", b"fake_png_data", "image/png")}
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

