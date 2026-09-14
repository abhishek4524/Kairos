"""
test_conversation_continuity.py — Verification of multi-turn conversation context retention.
"""

import pytest
import db
from llm_agent import get_chat_history, save_chat_history


def test_multi_turn_history_persistence():
    """Verify that multiple conversation turns save and reload context correctly."""
    session_id = "test_continuity_session_99"
    avatar_id = "avatar.vrm"

    # Clear any previous test session data
    db.clear_history(session_id, avatar_id)

    # Turn 1
    db.save_turn(session_id, avatar_id, "user", "My name is Abhishek and my favorite color is blue.")
    db.save_turn(session_id, avatar_id, "assistant", "Hello Abhishek! I have noted that your favorite color is blue.")

    hist_t1 = get_chat_history(session_id, avatar_id)
    assert len(hist_t1) == 2
    assert hist_t1[0]["content"] == "My name is Abhishek and my favorite color is blue."
    assert "favorite color is blue" in hist_t1[1]["content"]

    # Turn 2
    db.save_turn(session_id, avatar_id, "user", "What was my favorite color?")
    db.save_turn(session_id, avatar_id, "assistant", "Your favorite color is blue.")

    hist_t2 = get_chat_history(session_id, avatar_id)
    assert len(hist_t2) == 4
    assert hist_t2[2]["content"] == "What was my favorite color?"
    assert hist_t2[3]["content"] == "Your favorite color is blue."

    # Clean up
    db.clear_history(session_id, avatar_id)
