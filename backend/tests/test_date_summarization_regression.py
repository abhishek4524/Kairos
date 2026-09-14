"""
test_date_summarization_regression.py — Regression test for H.2 date/time query after summarization.
"""

import pytest
from unittest.mock import patch, MagicMock
from llm_agent import summarize_history_if_needed
from agents import orchestrator
from agent_tools import info_tools


def test_summarize_history_retains_tool_rule():
    """Verify that history summarization produces user/assistant turns with critical tool rules."""
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"Turn {i}"} for i in range(25)]

    mock_groq = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "Summary of 15 turns."
    mock_groq.chat.completions.create.return_value = mock_resp

    with patch("llm_agent.groq_client", mock_groq), \
         patch("db.clear_history"), \
         patch("db.save_turn"), \
         patch("llm_agent.save_chat_history"):
        new_hist = summarize_history_if_needed("session_h2", "avatar.vrm", history)

    # Ensure system turn is replaced with user/assistant context turn
    assert len(new_hist) < len(history)
    first_turn = new_hist[0]
    assert first_turn["role"] == "user"
    assert "Context Summary" in first_turn["content"]
    assert "get_current_datetime" in first_turn["content"]


def test_orchestrate_date_query_forces_realtime_datetime():
    """Verify that date/time queries execute get_current_datetime and inject verified system datetime."""
    mock_exec = MagicMock()
    mock_exec.return_value = {
        "date": "September 02, 2026",
        "time": "09:44 PM",
        "day_of_week": "Wednesday",
        "timezone": "Asia/Kolkata"
    }

    mock_orch = patch("agents.orchestrator.classify", return_value=("general_info", 0.99))

    with mock_orch:
        res = orchestrator.orchestrate(
            session_id="date_test_session",
            user_message="what is date today?",
            history=[],
            groq_client=None,
            execute_fn=mock_exec,
        )

    # Assert get_current_datetime tool was pre-executed
    mock_exec.assert_called_with("get_current_datetime", {})
    assert res.get("category") == "general_info"
