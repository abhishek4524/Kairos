"""
test_connectivity.py — Unit tests for Phase B (Connectivity State Machine & Local Readiness).
"""

import time
from unittest.mock import MagicMock, patch
import pytest

from core.connectivity import (
    ConnectivityManager,
    ConnectivityState,
    GOLDEN_RULE_FALLBACK_MESSAGE,
)


def test_valid_and_invalid_state_transitions():
    mgr = ConnectivityManager()
    assert mgr.current_state() == ConnectivityState.ONLINE

    # Invalid jump: ONLINE -> RECOVERING
    assert mgr.transition_to(ConnectivityState.RECOVERING) is False
    assert mgr.current_state() == ConnectivityState.ONLINE

    # Valid: ONLINE -> DEGRADED
    assert mgr.transition_to(ConnectivityState.DEGRADED, "latency high") is True
    assert mgr.current_state() == ConnectivityState.DEGRADED

    # Valid: DEGRADED -> ONLINE
    assert mgr.transition_to(ConnectivityState.ONLINE, "quick recovery") is True
    assert mgr.current_state() == ConnectivityState.ONLINE

    # Valid: ONLINE -> DEGRADED -> OFFLINE
    mgr.transition_to(ConnectivityState.DEGRADED)
    assert mgr.transition_to(ConnectivityState.OFFLINE, "timeout expired") is True
    assert mgr.current_state() == ConnectivityState.OFFLINE

    # Invalid: OFFLINE -> ONLINE directly
    assert mgr.transition_to(ConnectivityState.ONLINE) is False
    assert mgr.current_state() == ConnectivityState.OFFLINE

    # Valid: OFFLINE -> RECOVERING
    assert mgr.transition_to(ConnectivityState.RECOVERING, "ping ok") is True
    assert mgr.current_state() == ConnectivityState.RECOVERING

    # Valid: RECOVERING -> ONLINE
    assert mgr.transition_to(ConnectivityState.ONLINE, "groq check passed") is True
    assert mgr.current_state() == ConnectivityState.ONLINE


def test_recovering_flicker_back_to_offline():
    mgr = ConnectivityManager()
    mgr.transition_to(ConnectivityState.DEGRADED)
    mgr.transition_to(ConnectivityState.OFFLINE)
    mgr.transition_to(ConnectivityState.RECOVERING)

    # Flickered back off -> OFFLINE
    assert mgr.transition_to(ConnectivityState.OFFLINE, "verification failed") is True
    assert mgr.current_state() == ConnectivityState.OFFLINE


def test_health_check_state_machine_advancement():
    mgr = ConnectivityManager(auto_fallback=True, auto_recover=True)
    assert mgr.current_state() == ConnectivityState.ONLINE

    # Simulate cloud failure
    with patch.object(mgr, "is_cloud_available", return_value=False):
        mgr.check_health_and_update_state()
        assert mgr.current_state() == ConnectivityState.DEGRADED

        # Force degraded timer to simulate elapsed retry window
        mgr._degraded_since = time.time() - 6.0
        mgr.check_health_and_update_state()
        assert mgr.current_state() == ConnectivityState.OFFLINE

    # Simulate network returns
    with patch.object(mgr, "is_cloud_available", return_value=True):
        mgr.check_health_and_update_state()
        assert mgr.current_state() == ConnectivityState.RECOVERING

        # Groq check passes
        mgr.check_health_and_update_state()
        assert mgr.current_state() == ConnectivityState.ONLINE


def test_readiness_report_structure():
    mgr = ConnectivityManager()
    with patch.object(mgr._ollama, "health_check") as mock_h:
        mock_h.return_value = MagicMock(
            available=True,
            models_status={"qwen2.5:7b": True, "qwen2.5-coder:7b": True, "nomic-embed-text": True},
            details={"server_online": True},
        )
        report = mgr.get_readiness_report()
        assert "connectivity_state" in report
        assert "ollama_installed" in report
        assert "ollama_models" in report
        assert "system_resources" in report
        assert report["golden_rule_fallback_message"] == GOLDEN_RULE_FALLBACK_MESSAGE


def test_golden_rule_offline_missing_model_fallback(client):
    """When offline and local model is missing, verify endpoint/pipeline returns golden rule fallback message."""
    with patch("core.connectivity.current_state", return_value=ConnectivityState.OFFLINE), \
         patch("core.connectivity.get_readiness", return_value={
             "all_local_models_ready": False,
             "golden_rule_fallback_message": GOLDEN_RULE_FALLBACK_MESSAGE,
         }):

        res = client.get("/api/system/readiness")
        assert res.status_code == 200
        data = res.json()
        assert "Internet unavailable hai" in data["golden_rule_fallback_message"]
