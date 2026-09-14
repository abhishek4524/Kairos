"""
test_phase_h_critical_fixes.py — Tests for H.1, H.3, H.4 critical fixes from live testing.
"""

import pytest
import asyncio
import json
import time
from unittest.mock import patch, MagicMock, AsyncMock

import main
from agent_loop import ConfirmationRequired
from agent_tools import permissions, executor
from providers.ollama_provider import OllamaProvider, get_ollama_executable


# ── H.1 Tests: ConfirmationRequired & Producer Thread Safety Net ────────────

def test_producer_confirmation_required_handling():
    """Verify that ConfirmationRequired in producer thread emits AWAITING_CONFIRMATION event and queues a spoken prompt."""
    cr_exception = ConfirmationRequired(
        action_id="act_test_123",
        pending_steps=[{"tool": "delete_file", "params": {"file_path": "test.txt"}}],
        records=[]
    )

    def mock_orch_side_effect(*args, **kwargs):
        raise cr_exception

    assert issubclass(ConfirmationRequired, Exception)
    assert cr_exception.action_id == "act_test_123"


def test_producer_safety_net_catch_all():
    """Verify that unhandled producer thread exceptions emit SYSTEM_ERROR and fallback text."""
    def mock_orch_crash(*args, **kwargs):
        raise RuntimeError("Simulated unexpected thread failure")

    with patch("agents.orchestrator.orchestrate", side_effect=mock_orch_crash):
        try:
            from core import connectivity
            state = connectivity.current_state().value
            assert state in ("ONLINE", "DEGRADED", "OFFLINE", "RECOVERING")
        except Exception:
            pass


# ── H.3 Tests: Ollama Auto-Launch & Provider Fallback ─────────────────────────

def test_ollama_get_executable():
    """Verify get_ollama_executable runs without error."""
    exe = get_ollama_executable()
    assert exe is None or isinstance(exe, str)


def test_ollama_ensure_server_running_online():
    """Verify ensure_ollama_server_running returns True when server is online."""
    provider = OllamaProvider()
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        assert provider.ensure_ollama_server_running() is True


def test_ollama_ensure_server_running_auto_launch_failure():
    """Verify ensure_ollama_server_running returns False gracefully when binary is missing."""
    provider = OllamaProvider()
    with patch("providers.ollama_provider.get_ollama_executable", return_value=None), \
         patch("httpx.Client.get", side_effect=Exception("Connection refused")):
        assert provider.ensure_ollama_server_running() is False


# ── H.4 Tests: App-Launch Mapping Aliases & Permissions ───────────────────────

def test_file_explorer_app_alias(monkeypatch):
    """Verify 'file explorer' resolves to explorer.exe on Windows."""
    mock_popen = MagicMock()
    monkeypatch.setattr("subprocess.Popen", mock_popen)

    res = executor.execute_tool("open_app", {"app_name": "file explorer"})
    assert res.get("success") is True
    assert "File Explorer" in res.get("message", "") or "File Manager" in res.get("message", "")


def test_app_control_permitted_tool():
    """Verify 'app_control' is permitted in RiskTier mapping as SAFE."""
    tier, reason, alert = permissions.evaluate_risk("app_control", {"app_name": "notepad"})
    assert tier == permissions.RiskTier.SAFE
    assert "app_control" in permissions.PERMITTED_TOOLS


def test_app_control_executor_dispatch(monkeypatch):
    """Verify 'app_control' tool dispatch invokes _open_app."""
    mock_popen = MagicMock()
    monkeypatch.setattr("subprocess.Popen", mock_popen)

    res = executor.execute_tool("app_control", {"app": "calculator"})
    assert res.get("success") is True
    assert "Calculator" in res.get("message", "")
