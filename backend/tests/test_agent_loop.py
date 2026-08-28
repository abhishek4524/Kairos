"""
test_agent_loop.py — Unit tests for the PLAN → EXECUTE → REFLECT → RETRY agentic loop.

All external calls (Groq LLM, executor.execute_tool) are fully mocked.
No real browsers, files, or network calls are made.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock, call
from typing import List

# ── Path setup ─────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agent_loop
from agent_loop import (
    classify_complexity,
    run_plan_phase,
    run_reflect_phase,
    run_agentic_loop,
    AgentLoopResult,
    ConfirmationRequired,
    Step,
    ReflectResult,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_groq_response(content: str) -> MagicMock:
    """Build a fake non-streaming Groq completion response."""
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_groq_client(*responses) -> MagicMock:
    """Build a Groq client whose create() returns the given responses in sequence."""
    client = MagicMock()
    client.chat.completions.create.side_effect = list(responses)
    return client


_NOOP_EMIT = lambda event, payload: None  # noqa: E731


# ── classify_complexity ────────────────────────────────────────────────────────

class TestClassifyComplexity:
    def test_simple_short_command(self):
        assert classify_complexity("pause the video") == "simple"

    def test_simple_open_app(self):
        assert classify_complexity("open Brave") == "simple"

    def test_complex_and_then_keyword(self):
        assert classify_complexity("open YouTube and then search for lofi music") == "complex"

    def test_complex_first_then_keyword(self):
        assert classify_complexity("first open YouTube, then search lofi, finally play it") == "complex"

    def test_complex_long_utterance(self):
        msg = "go to youtube search for lofi hip hop music and play the second video please"
        assert classify_complexity(msg) == "complex"

    def test_simple_borderline_word_count(self):
        # Exactly 12 words — not above threshold, no keywords
        msg = "open youtube and search for lofi music and play it"
        # "and" keyword triggers complex here via ", and " pattern check
        # Actually "and " is not in our pattern — "and then" is. Let's use a clean 12-word sentence:
        msg = "navigate to the python documentation website for me please now"
        # 10 words — simple
        assert classify_complexity(msg) == "simple"

    def test_complex_comma_and_conjunction(self):
        assert classify_complexity("search lofi music, and play the second video") == "complex"


# ── run_plan_phase ─────────────────────────────────────────────────────────────

class TestRunPlanPhase:
    def test_parses_valid_plan_json(self):
        plan_json = '{"steps": [{"tool": "navigate_to", "params": {"url_or_search_query": "youtube.com"}, "purpose": "Open YouTube"}, {"tool": "type_into", "params": {"description": "search box", "text": "lofi"}, "purpose": "Search lofi"}]}'
        client = _make_groq_client(_make_groq_response(plan_json))
        steps = run_plan_phase("open youtube and search lofi", client, "test-model")
        assert len(steps) == 2
        assert steps[0].tool == "navigate_to"
        assert steps[0].params["url_or_search_query"] == "youtube.com"
        assert steps[1].tool == "type_into"

    def test_strips_markdown_fences(self):
        plan_json = '```json\n{"steps": [{"tool": "open_app", "params": {"app_name": "brave"}, "purpose": "Open Brave"}]}\n```'
        client = _make_groq_client(_make_groq_response(plan_json))
        steps = run_plan_phase("open brave", client, "test-model")
        assert steps[0].tool == "open_app"

    def test_falls_back_on_invalid_json(self):
        client = _make_groq_client(_make_groq_response("not json at all !!!"))
        steps = run_plan_phase("do something", client, "test-model")
        assert len(steps) == 1
        assert steps[0].is_direct_response

    def test_handles_respond_directly_step(self):
        plan_json = '{"steps": [{"tool": "respond_directly", "response_text": "I cannot do that.", "purpose": "Explain limitation"}]}'
        client = _make_groq_client(_make_groq_response(plan_json))
        steps = run_plan_phase("fly to mars", client, "test-model")
        assert steps[0].is_direct_response
        assert steps[0].response_text == "I cannot do that."


# ── run_reflect_phase ──────────────────────────────────────────────────────────

class TestRunReflectPhase:
    def test_success_reflect(self):
        reflect_json = '{"success": true, "reason": "YouTube loaded fine", "revised_step": null}'
        client = _make_groq_client(_make_groq_response(reflect_json))
        step = Step(tool="navigate_to", params={"url_or_search_query": "youtube.com"}, purpose="Open YouTube")
        result = {"success": True, "url": "https://youtube.com"}
        reflect = run_reflect_phase(step, result, "open youtube", client, "test-model")
        assert reflect.success is True
        assert "YouTube" in reflect.reason
        assert reflect.revised_step is None

    def test_failure_reflect_with_revision(self):
        reflect_json = '{"success": false, "reason": "Element not found", "revised_step": {"tool": "find_and_click", "params": {"description": "second search result"}, "purpose": "Click second result"}}'
        client = _make_groq_client(_make_groq_response(reflect_json))
        step = Step(tool="find_and_click", params={"description": "second video"}, purpose="Click second video")
        result = {"success": False, "message": "No element matching 'second video'"}
        reflect = run_reflect_phase(step, result, "play second video", client, "test-model")
        assert reflect.success is False
        assert reflect.revised_step is not None
        assert reflect.revised_step.params["description"] == "second search result"

    def test_fallback_on_reflect_error(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = Exception("API error")
        step = Step(tool="navigate_to", params={}, purpose="Navigate")
        result = {"success": True}
        reflect = run_reflect_phase(step, result, "navigate", client, "test-model")
        # Falls back to trusting executor success flag
        assert reflect.success is True


# ── run_agentic_loop ───────────────────────────────────────────────────────────

class TestAgenticLoop:

    def _plan_response(self, steps_list):
        import json
        return _make_groq_response(json.dumps({"steps": steps_list}))

    def _reflect_ok(self):
        return _make_groq_response('{"success": true, "reason": "Step succeeded", "revised_step": null}')

    def _reflect_fail_with_revision(self, revised_tool, revised_params, revised_purpose):
        import json
        return _make_groq_response(json.dumps({
            "success": False,
            "reason": "Element not found",
            "revised_step": {"tool": revised_tool, "params": revised_params, "purpose": revised_purpose}
        }))

    def _narrate_ok(self):
        return _make_groq_response("Done! All steps completed for you, Abhishek!")

    def _narrate_fail(self):
        return _make_groq_response("I wasn't able to complete that after retrying.")

    # ── Test 1: succeeds first try ─────────────────────────────────────────────

    def test_loop_succeeds_first_try(self):
        """Two-step plan; both tools return success=True; 0 retries used."""
        plan_steps = [
            {"tool": "navigate_to", "params": {"url_or_search_query": "youtube.com"}, "purpose": "Open YouTube"},
            {"tool": "type_into", "params": {"description": "search box", "text": "lofi"}, "purpose": "Search lofi"},
        ]
        groq_client = _make_groq_client(
            self._plan_response(plan_steps),   # PLAN call
            self._reflect_ok(),                # REFLECT step 1
            self._reflect_ok(),                # REFLECT step 2
            self._narrate_ok(),                # NARRATE
        )

        events = []
        def emit(event, payload):
            events.append(event)

        execute_results = [
            {"success": True, "message": "Navigated to YouTube"},
            {"success": True, "message": "Typed lofi into search box"},
        ]
        execute_fn = MagicMock(side_effect=execute_results)

        result = run_agentic_loop(
            user_message="open youtube and search lofi",
            history=[],
            groq_client=groq_client,
            model="test-model",
            emit_event_fn=emit,
            execute_fn=execute_fn,
        )

        assert result.exhausted is False
        assert result.total_retries == 0
        assert len(result.steps_executed) == 2
        assert "TOOL_EXECUTION" in events
        assert "THINKING" in events
        assert "SUCCESS" in events
        assert "ERROR" not in events
        execute_fn.assert_any_call("navigate_to", {"url_or_search_query": "youtube.com"})
        execute_fn.assert_any_call("type_into", {"description": "search box", "text": "lofi"})

    # ── Test 2: fails once then succeeds on retry ──────────────────────────────

    def test_loop_retries_once_then_succeeds(self):
        """Step 2 fails first attempt; REFLECT provides revision; retry succeeds."""
        plan_steps = [
            {"tool": "navigate_to", "params": {"url_or_search_query": "youtube.com"}, "purpose": "Open YouTube"},
            {"tool": "find_and_click", "params": {"description": "second video"}, "purpose": "Click second video"},
        ]
        groq_client = _make_groq_client(
            self._plan_response(plan_steps),   # PLAN
            self._reflect_ok(),                # REFLECT step 1 ok
            self._reflect_fail_with_revision(  # REFLECT step 2 fail → revised
                "find_and_click",
                {"description": "second search result"},
                "Click second search result"
            ),
            self._reflect_ok(),                # REFLECT step 2 retry ok
            self._narrate_ok(),                # NARRATE
        )

        execute_results = [
            {"success": True, "message": "YouTube loaded"},           # step 1
            {"success": False, "message": "Element not found"},       # step 2 attempt 1
            {"success": True, "message": "Clicked second result"},    # step 2 retry
        ]
        execute_fn = MagicMock(side_effect=execute_results)

        events = []
        result = run_agentic_loop(
            user_message="open youtube and play second video",
            history=[],
            groq_client=groq_client,
            model="test-model",
            emit_event_fn=lambda e, p: events.append(e),
            execute_fn=execute_fn,
        )

        assert result.exhausted is False
        assert result.total_retries == 1
        assert execute_fn.call_count == 3
        assert "THINKING" in events
        assert "SUCCESS" in events

    # ── Test 3: exhausts all retries, graceful failure ─────────────────────────

    def test_loop_exhausts_retries_graceful_failure(self):
        """A step fails all MAX_RETRIES attempts → exhausted=True, no ERROR exception raised."""
        plan_steps = [
            {"tool": "find_and_click", "params": {"description": "nonexistent button"}, "purpose": "Click button"},
        ]
        # Enough reflect responses for 3 failure attempts + narrate
        fail_reflect = lambda: _make_groq_response('{"success": false, "reason": "Not found", "revised_step": {"tool": "find_and_click", "params": {"description": "button v2"}, "purpose": "try again"}}')
        groq_client = _make_groq_client(
            self._plan_response(plan_steps),  # PLAN
            fail_reflect(),                   # REFLECT attempt 0
            fail_reflect(),                   # REFLECT attempt 1
            fail_reflect(),                   # REFLECT attempt 2
            self._narrate_fail(),             # exhaustion narration
        )

        execute_fn = MagicMock(return_value={"success": False, "message": "Element not found"})
        events = []

        result = run_agentic_loop(
            user_message="click a nonexistent button",
            history=[],
            groq_client=groq_client,
            model="test-model",
            emit_event_fn=lambda e, p: events.append(e),
            execute_fn=execute_fn,
            max_retries=3,
        )

        assert result.exhausted is True
        assert result.total_retries >= 2
        assert "ERROR" in events
        assert "SUCCESS" not in events
        # The narrated failure message should be present
        assert result.summary_text != ""

    # ── Test 4: confirm simple path bypasses loop ──────────────────────────────

    def test_simple_classify_does_not_engage_loop(self):
        """classify_complexity returns 'simple' for short single-action command."""
        assert classify_complexity("pause the video") == "simple"
        assert classify_complexity("open Brave") == "simple"
        assert classify_complexity("close calculator") == "simple"

    # ── Test 5: complex classify engages loop ──────────────────────────────────

    def test_complex_classify_engages_loop(self):
        """classify_complexity returns 'complex' for multi-step commands."""
        assert classify_complexity("open youtube and then search lofi music and play the second video") == "complex"
        assert classify_complexity("first navigate to github, then search kairos repo, and finally clone it") == "complex"

    # ── Test 6: direct-response step is recorded without executor call ─────────

    def test_direct_response_step_skips_executor(self):
        plan_steps = [
            {"tool": "respond_directly", "response_text": "I can not do that.", "purpose": "Explain"},
        ]
        groq_client = _make_groq_client(
            self._plan_response(plan_steps),  # PLAN
            self._narrate_ok(),               # NARRATE
        )
        execute_fn = MagicMock()

        result = run_agentic_loop(
            user_message="fly to mars",
            history=[],
            groq_client=groq_client,
            model="test-model",
            emit_event_fn=_NOOP_EMIT,
            execute_fn=execute_fn,
        )

        execute_fn.assert_not_called()
        assert result.exhausted is False
        assert len(result.steps_executed) == 1

    # ── Test 7: ConfirmationRequired is raised mid-plan ───────────────────────

    def test_loop_raises_confirmation_required_mid_plan(self):
        """When execute_fn returns requires_confirmation=True, ConfirmationRequired is raised."""
        plan_steps = [
            {"tool": "navigate_to", "params": {"url_or_search_query": "youtube.com"}, "purpose": "Open YouTube"},
            {"tool": "send_whatsapp_message", "params": {"recipient": "Vansh", "message": "hi"}, "purpose": "Send message"},
        ]
        groq_client = _make_groq_client(
            self._plan_response(plan_steps),  # PLAN
            self._reflect_ok(),               # REFLECT step 1 ok
        )

        execute_results = [
            {"success": True, "message": "YouTube loaded"},
            {
                "success": False,
                "requires_confirmation": True,
                "action_id": "test-action-001",
                "confirmation_prompt": "Send 'hi' to Vansh?",
            },
        ]
        execute_fn = MagicMock(side_effect=execute_results)

        with pytest.raises(ConfirmationRequired) as exc_info:
            run_agentic_loop(
                user_message="open youtube and send hi to Vansh",
                history=[],
                groq_client=groq_client,
                model="test-model",
                emit_event_fn=_NOOP_EMIT,
                execute_fn=execute_fn,
            )

        assert exc_info.value.action_id == "test-action-001"
        # Remaining steps should include only the current paused step
        assert len(exc_info.value.pending_steps) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
