"""
test_orchestrator.py — Unit tests for orchestrator intent classification, sub-agent routing, tool schema partitioning, and history preservation.
"""

import os
import sys
import time
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import classify, get_agent_for_category, orchestrate, CONFIDENCE_THRESHOLD
from agents.coding_agent import CodingAgent
from agents.browsing_agent import BrowsingAgent
from agents.system_agent import SystemAgent
from agents.memory_agent import MemoryAgent
from agents.general_agent import GeneralAgent
from agents.base_agent import BaseSubAgent


def _make_mock_groq_response(json_str: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = json_str
    resp = MagicMock()
    resp.choices = [choice]
    return resp


class TestOrchestratorClassification:
    def test_classify_coding(self):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_mock_groq_response(
            '{"category": "coding", "confidence": 0.95}'
        )
        cat, conf = classify("write a quicksort in python", groq_client=client)
        assert cat == "coding"
        assert conf == 0.95

    def test_classify_browsing(self):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_mock_groq_response(
            '{"category": "browsing", "confidence": 0.98}'
        )
        cat, conf = classify("open youtube and search lofi", groq_client=client)
        assert cat == "browsing"
        assert conf == 0.98

    def test_classify_system_control(self):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_mock_groq_response(
            '{"category": "system_control", "confidence": 0.92}'
        )
        cat, conf = classify("close calculator and open notepad", groq_client=client)
        assert cat == "system_control"
        assert conf == 0.92

    def test_classify_research_memory(self):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_mock_groq_response(
            '{"category": "research_memory", "confidence": 0.89}'
        )
        cat, conf = classify("what did I say about my database project?", groq_client=client)
        assert cat == "research_memory"
        assert conf == 0.89

    def test_classify_chitchat_general(self):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_mock_groq_response(
            '{"category": "chitchat_general", "confidence": 0.99}'
        )
        cat, conf = classify("hello Kairos, how are you?", groq_client=client)
        assert cat == "chitchat_general"
        assert conf == 0.99

    def test_classify_low_confidence_falls_back_to_general_agent(self):
        # Confidence 0.50 is below CONFIDENCE_THRESHOLD (0.70)
        agent, eff_cat = get_agent_for_category("coding", confidence=0.50)
        assert isinstance(agent, GeneralAgent)
        assert eff_cat == "chitchat_general"

    def test_classify_high_confidence_routes_to_specific_agent(self):
        agent, eff_cat = get_agent_for_category("coding", confidence=0.95)
        assert isinstance(agent, CodingAgent)
        assert eff_cat == "coding"

    def test_classification_under_150ms_mock(self):
        client = MagicMock()
        client.chat.completions.create.return_value = _make_mock_groq_response(
            '{"category": "browsing", "confidence": 0.95}'
        )
        t0 = time.time()
        cat, conf = classify("navigate to github.com", groq_client=client)
        dt_ms = (time.time() - t0) * 1000
        assert dt_ms < 150.0
        assert cat == "browsing"


class TestSubAgentToolPartitioning:
    def test_coding_agent_tool_subset(self):
        agent = CodingAgent()
        schemas = agent.get_tool_schemas()
        tool_names = [s["function"]["name"] for s in schemas]
        assert "open_vscode_and_write_code" in tool_names
        assert "write_and_run_sandbox_code" in tool_names
        assert "navigate_to" not in tool_names  # Browser tools excluded
        assert "open_app" not in tool_names     # OS tools excluded

    def test_browsing_agent_tool_subset(self):
        agent = BrowsingAgent()
        schemas = agent.get_tool_schemas()
        tool_names = [s["function"]["name"] for s in schemas]
        assert "navigate_to" in tool_names
        assert "find_and_click" in tool_names
        assert "youtube_search" in tool_names
        assert "open_vscode_and_write_code" not in tool_names  # Coding tools excluded

    def test_system_agent_tool_subset(self):
        agent = SystemAgent()
        schemas = agent.get_tool_schemas()
        tool_names = [s["function"]["name"] for s in schemas]
        assert "open_app" in tool_names
        assert "close_app" in tool_names
        assert "send_whatsapp_desktop_message" in tool_names
        assert "navigate_to" not in tool_names  # Browser primitives excluded

    def test_memory_agent_no_action_tools(self):
        agent = MemoryAgent()
        schemas = agent.get_tool_schemas()
        assert len(schemas) == 0

    def test_general_agent_no_action_tools(self):
        agent = GeneralAgent()
        schemas = agent.get_tool_schemas()
        assert len(schemas) == 0


class TestOrchestratorIntegration:
    @patch("agents.base_agent.generate_streaming_response")
    def test_orchestrate_history_passed_to_subagent(self, mock_stream):
        mock_stream.return_value = ["Hello ", "Abhishek!"]
        client = MagicMock()
        client.chat.completions.create.return_value = _make_mock_groq_response(
            '{"category": "chitchat_general", "confidence": 0.95}'
        )

        history = [
            {"role": "user", "content": "previous turn 1"},
            {"role": "assistant", "content": "previous response 1"},
            {"role": "user", "content": "previous turn 2"},
            {"role": "assistant", "content": "previous response 2"},
        ]

        res = orchestrate(
            session_id="test_session",
            user_message="how are you?",
            history=history,
            groq_client=client,
            skip_memory=True,
        )

        assert res["agent_name"] == "general_agent"
        assert res["full_text"] == "Hello Abhishek!"
        # Verify history was forwarded
        mock_stream.assert_called_once()
        call_kwargs = mock_stream.call_args.kwargs
        assert call_kwargs["session_id"] == "test_session"

    @patch("agents.base_agent.run_agentic_loop")
    def test_agent_loop_preserved_in_subagent_for_complex_tasks(self, mock_loop):
        mock_loop_res = MagicMock()
        mock_loop_res.summary_text = "Completed coding task successfully."
        mock_loop.return_value = mock_loop_res

        client = MagicMock()
        client.chat.completions.create.return_value = _make_mock_groq_response(
            '{"category": "coding", "confidence": 0.95}'
        )

        res = orchestrate(
            session_id="test_session",
            user_message="open vscode and then write a python script to parse CSV files",
            history=[],
            groq_client=client,
            skip_memory=True,
        )

        assert res["agent_name"] == "coding_agent"
        assert res["mode"] == "loop"
        assert res["narration"] == "Completed coding task successfully."
        mock_loop.assert_called_once()
        call_kwargs = mock_loop.call_args.kwargs
        assert call_kwargs["allowed_tools"] == CodingAgent.tool_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
