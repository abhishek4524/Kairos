"""
test_llm_agent.py — Unit tests for LLM Agent prompt building, action parsing, and output sanitization.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import llm_agent
from agent_tools.executor import extract_action, strip_action_tag


def test_extract_action_valid_json():
    text = '[ACTION:{"tool":"navigate_to","params":{"url_or_search_query":"https://example.com"},"summary":"Navigating"}] Navigating now!'
    action = extract_action(text)
    assert action is not None
    assert action["tool"] == "navigate_to"
    assert action["params"]["url_or_search_query"] == "https://example.com"


def test_extract_action_slightly_broken_json():
    # Missing closing brace
    text = '[ACTION:{"tool":"scroll_page","params":{"direction":"down"}'
    action = extract_action(text)
    assert action is not None
    assert action["tool"] == "scroll_page"
    assert action["params"]["direction"] == "down"


def test_extract_action_none_when_absent():
    text = "Hello Abhishek! How can I help you today?"
    assert extract_action(text) is None


def test_strip_action_tag():
    text = '[ACTION:{"tool":"open_app","params":{"app_name":"brave"}}] Opening Brave for you!'
    cleaned = strip_action_tag(text)
    assert cleaned == "Opening Brave for you!"


def test_strip_emotion_tag():
    cases = [
        ("[happy]: Hello Abhishek!", "Hello Abhishek!"),
        ("[thinking] Let me check that for you.", "Let me check that for you."),
        ("[neutral]: I have found the file.", "I have found the file."),
        ("No emotion prefix here.", "No emotion prefix here."),
    ]
    for raw, expected in cases:
        assert llm_agent.strip_emotion_tag(raw) == expected


def test_clean_llm_output_reasoning_and_think_tags():
    raw = """<think>
Need to open Brave and search for python.
</think>
**Reasoning**
The user requested python documentation.
**Final Answer**
[happy]: I am navigating to the Python documentation for you, Abhishek!"""
    cleaned = llm_agent.clean_llm_output(raw)
    assert "<think>" not in cleaned
    assert "Reasoning" not in cleaned
    assert "Final Answer" not in cleaned
    assert cleaned == "I am navigating to the Python documentation for you, Abhishek!"


def test_system_prompt_includes_tools_and_rules():
    prompt = llm_agent.get_system_prompt("en")
    assert "Arya" in prompt
    assert "Abhishek" in prompt

    assert "navigate_to" in prompt
    assert "find_and_click" in prompt
    assert "DESKTOP & WEB AUTOMATION TOOLS" in prompt


@patch("core.provider_router.route_chat")
def test_generate_streaming_response_groq(mock_route_chat):
    def _fake_stream():
        yield "Hello "
        yield "Abhishek!"

    mock_route_chat.return_value = (_fake_stream(), "groq")

    chunks = list(llm_agent.generate_streaming_response(
        session_id="test_session",
        user_message="Hello",
        skip_memory=True
    ))

    assert "".join(chunks) == "Hello Abhishek!"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
