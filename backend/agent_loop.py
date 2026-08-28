"""
agent_loop.py — PLAN → EXECUTE → REFLECT → RETRY agentic reasoning loop for Kairos.

Architecture:
  1. classify_complexity()  — fast keyword heuristic, no LLM call.
  2. run_plan_phase()        — single non-streaming Groq call returning structured JSON steps.
  3. run_reflect_phase()     — single non-streaming Groq call judging step outcome.
  4. run_agentic_loop()      — orchestrates the full loop with WebSocket state emissions.

The loop is only engaged for COMPLEX requests.  Simple single-tool commands ("pause the
video", "open Brave") continue through the existing fast streaming path unchanged.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional

logger = logging.getLogger("kairos.agent_loop")

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_RETRIES = 3         # max retry attempts per step
PLAN_MAX_TOKENS = 512   # plan call is compact JSON
REFLECT_MAX_TOKENS = 256

# Keywords that signal multi-step user intent
_COMPLEX_KEYWORDS = [
    "and then", "then ", "after that", "first ", "finally",
    "step 1", "also ", ", and ", "; and", "followed by",
    "search for.*and.*play", "open.*search.*click", "navigate.*type.*click",
]
_COMPLEX_KW_RE = re.compile("|".join(_COMPLEX_KEYWORDS), re.IGNORECASE)

# Word-count threshold: utterances longer than this are presumed complex
_COMPLEX_WORD_THRESHOLD = 12


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class Step:
    """A single planned action."""
    tool: str
    params: Dict[str, Any]
    purpose: str
    # Direct-response steps skip executor; the text is spoken/returned instead
    response_text: Optional[str] = None

    @property
    def is_direct_response(self) -> bool:
        return self.tool == "respond_directly"


@dataclass
class ReflectResult:
    success: bool
    reason: str
    revised_step: Optional[Step] = None


@dataclass
class StepRecord:
    """Log entry for one execution attempt of a step."""
    step_index: int
    attempt: int
    tool: str
    params: Dict[str, Any]
    purpose: str
    result: Dict[str, Any]
    reflect: Optional[ReflectResult]
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentLoopResult:
    summary_text: str
    steps_executed: List[StepRecord]
    total_retries: int
    exhausted: bool          # True if any step ran out of retries
    requires_confirmation: bool = False
    action_id: Optional[str] = None
    pending_steps: Optional[List[Step]] = None   # remaining plan after pause


class ConfirmationRequired(Exception):
    """Raised by run_agentic_loop when a step needs user confirmation."""
    def __init__(self, action_id: str, pending_steps: List[Step], records: List[StepRecord]):
        super().__init__(f"Confirmation required: {action_id}")
        self.action_id = action_id
        self.pending_steps = pending_steps
        self.records = records


# ── Complexity classifier ─────────────────────────────────────────────────────

def classify_complexity(user_message: str) -> Literal["simple", "complex"]:
    """
    Fast, zero-latency heuristic.  No LLM call.

    Returns "complex" when:
      - The message contains multi-step conjunction keywords, OR
      - The message word-count exceeds the threshold.
    Returns "simple" otherwise.
    """
    msg = user_message.strip()
    if _COMPLEX_KW_RE.search(msg):
        logger.debug("[classify] complex (keyword match): %r", msg[:60])
        return "complex"
    word_count = len(msg.split())
    if word_count > _COMPLEX_WORD_THRESHOLD:
        logger.debug("[classify] complex (word count %d): %r", word_count, msg[:60])
        return "complex"
    logger.debug("[classify] simple: %r", msg[:60])
    return "simple"


# ── Plan phase ────────────────────────────────────────────────────────────────

_ALL_TOOLS = (
    "navigate_to, find_and_click, type_into, scroll_page, extract_page_text, go_back, "
    "open_new_tab, switch_tab, open_app, close_app, cursor_control, type_in_active_window, "
    "open_notepad_and_write_code, open_vscode_and_write_code, write_and_run_sandbox_code, "
    "delete_file, send_email, send_whatsapp_message, check_whatsapp_notifications, "
    "send_whatsapp_desktop_message, youtube_search, youtube_play_video, youtube_control, "
    "work_mode, respond_directly"
)

_PLAN_SYSTEM_TEMPLATE = (
    "You are a task planner for Kairos AI assistant.\n"
    "Given the user's request and available tool names, return ONLY valid JSON — no prose, no markdown fences.\n"
    "Format:\n"
    '{{\n  "steps": [\n    {{"tool": "<tool_name>", "params": {{<params>}}, "purpose": "<one sentence>"}},\n    ...\n  ]\n}}\n'
    "Use \"respond_directly\" as the tool name (with \"response_text\" key instead of params) when no action tool is needed.\n"
    "Keep steps minimal and ordered.  Maximum 6 steps.\n"
    "Available tools: {tools}.\n"
)


def _build_plan_system(allowed_tools: Optional[List[str]] = None) -> str:
    tools_str = ", ".join(list(allowed_tools) + ["respond_directly"]) if allowed_tools else _ALL_TOOLS
    return _PLAN_SYSTEM_TEMPLATE.format(tools=tools_str)


def run_plan_phase(
    user_message: str,
    groq_client,
    model: str,
    history: Optional[List[Dict]] = None,
    allowed_tools: Optional[List[str]] = None,
) -> List[Step]:
    """
    Ask the LLM to decompose the user message into an ordered list of Steps.
    Returns parsed Step objects.  Falls back to a single respond_directly step on error.
    """
    logger.info("[PLAN] planning for: %r", user_message[:80])

    messages = [{"role": "system", "content": _build_plan_system(allowed_tools)}]
    # Inject a tiny slice of history for context (last 2 turns max)
    if history:
        for turn in history[-4:]:
            messages.append(turn)
    messages.append({"role": "user", "content": user_message})

    try:
        resp = groq_client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False,
            max_tokens=PLAN_MAX_TOKENS,
            temperature=0.2,
        )
        raw = resp.choices[0].message.content.strip()
        logger.debug("[PLAN] raw response: %s", raw)

        # Strip markdown fences if model wrapped anyway
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        data = json.loads(raw)
        steps = []
        for s in data.get("steps", []):
            if s.get("tool") == "respond_directly":
                steps.append(Step(
                    tool="respond_directly",
                    params={},
                    purpose=s.get("purpose", ""),
                    response_text=s.get("response_text", ""),
                ))
            else:
                steps.append(Step(
                    tool=s["tool"],
                    params=s.get("params", {}),
                    purpose=s.get("purpose", ""),
                ))
        if not steps:
            raise ValueError("Empty steps array")
        logger.info("[PLAN] produced %d step(s)", len(steps))
        return steps

    except Exception as exc:
        logger.warning("[PLAN] failed (%s); falling back to single respond_directly", exc)
        return [Step(
            tool="respond_directly",
            params={},
            purpose="Fallback direct response",
            response_text=f"I had trouble planning that, sir. {user_message}",
        )]


# ── Reflect phase ─────────────────────────────────────────────────────────────

_REFLECT_SYSTEM = """\
You are a step-outcome evaluator for Kairos AI assistant.
Given the step that was executed and its result, decide if it succeeded and satisfied its purpose.
Return ONLY valid JSON — no prose, no markdown fences.
Format:
{"success": true|false, "reason": "<brief sentence>", "revised_step": null | {"tool":"...","params":{...},"purpose":"..."}}
Set revised_step to a corrected version of the step only when success is false and a fix is possible.
"""


def run_reflect_phase(
    step: Step,
    result: Dict[str, Any],
    user_message: str,
    groq_client,
    model: str,
) -> ReflectResult:
    """
    Ask the LLM to judge whether the executed step succeeded.
    Returns a ReflectResult with optional revised_step for retry.
    """
    logger.info("[REFLECT] evaluating step tool=%s success=%s", step.tool, result.get("success"))

    content = (
        f"User request: {user_message}\n\n"
        f"Step executed:\n  tool: {step.tool}\n  params: {json.dumps(step.params)}\n  purpose: {step.purpose}\n\n"
        f"Execution result:\n{json.dumps(result, default=str)}"
    )
    messages = [
        {"role": "system", "content": _REFLECT_SYSTEM},
        {"role": "user", "content": content},
    ]

    try:
        resp = groq_client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False,
            max_tokens=REFLECT_MAX_TOKENS,
            temperature=0.1,
        )
        raw = resp.choices[0].message.content.strip()
        logger.debug("[REFLECT] raw response: %s", raw)
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        data = json.loads(raw)

        revised_step = None
        if not data.get("success") and data.get("revised_step"):
            rs = data["revised_step"]
            revised_step = Step(
                tool=rs["tool"],
                params=rs.get("params", {}),
                purpose=rs.get("purpose", step.purpose),
            )

        return ReflectResult(
            success=bool(data.get("success", False)),
            reason=data.get("reason", ""),
            revised_step=revised_step,
        )

    except Exception as exc:
        logger.warning("[REFLECT] failed (%s); assuming success based on result dict", exc)
        # Fall back: trust the executor's own success flag
        return ReflectResult(
            success=bool(result.get("success", False)),
            reason=f"Reflect call failed ({exc}); using executor success flag",
        )


# ── Narrate final result ──────────────────────────────────────────────────────

_NARRATE_SYSTEM = """\
You are Kairos, a friendly personal AI assistant.  Given a summary of completed steps,
write ONE natural English sentence (max 20 words) confirming what was done.  No bullet lists.
"""

_EXHAUSTED_SYSTEM = """\
You are Kairos, a friendly personal AI assistant.  A multi-step task failed after all retries.
Write ONE clear, empathetic English sentence explaining what went wrong and what the user can try.
"""


def _narrate_completion(user_message: str, records: List[StepRecord], groq_client, model: str) -> str:
    """Generate a brief spoken completion sentence."""
    summary_lines = []
    for r in records:
        outcome = "succeeded" if (r.reflect and r.reflect.success) or r.result.get("success") else "had issues"
        summary_lines.append(f"Step {r.step_index+1} ({r.tool} — {r.purpose}): {outcome}")

    content = f"User asked: {user_message}\n\nSteps:\n" + "\n".join(summary_lines)
    try:
        resp = groq_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _NARRATE_SYSTEM},
                {"role": "user", "content": content},
            ],
            stream=False, max_tokens=60, temperature=0.4,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return "Done! All steps completed for you, sir."


def _narrate_exhaustion(user_message: str, last_reason: str, groq_client, model: str) -> str:
    """Generate a spoken failure explanation."""
    content = f"Task: {user_message}\nLast failure reason: {last_reason}"
    try:
        resp = groq_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _EXHAUSTED_SYSTEM},
                {"role": "user", "content": content},
            ],
            stream=False, max_tokens=60, temperature=0.4,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return f"I wasn't able to complete that after multiple attempts — {last_reason}. Please try again."


# ── Agentic loop orchestrator ─────────────────────────────────────────────────

def run_agentic_loop(
    user_message: str,
    history: List[Dict],
    groq_client,
    model: str,
    emit_event_fn: Callable[[str, Dict], Any],   # sync or async; main.py wraps as needed
    execute_fn: Callable[[str, Dict], Dict],      # calls executor.execute_tool
    max_retries: int = MAX_RETRIES,
    allowed_tools: Optional[List[str]] = None,
) -> AgentLoopResult:
    """
    Full PLAN → EXECUTE → REFLECT → RETRY/DONE loop.

    emit_event_fn(event_name, payload) is called at each phase transition.
    execute_fn(tool_name, params) wraps executor.execute_tool.

    Raises ConfirmationRequired if a step needs user confirmation mid-loop.
    Returns AgentLoopResult on completion (success or exhaustion).
    """
    records: List[StepRecord] = []
    total_retries = 0
    any_exhausted = False

    # ── PLAN ─────────────────────────────────────────────────────────────────
    emit_event_fn("PROCESSING_INPUT", {"phase": "plan", "message": user_message})
    logger.info("[LOOP] PLAN phase begin")
    steps = run_plan_phase(user_message, groq_client, model, history, allowed_tools=allowed_tools)
    logger.info("[LOOP] PLAN produced %d steps: %s", len(steps), [s.tool for s in steps])

    # ── EXECUTE each step ────────────────────────────────────────────────────
    for step_idx, step in enumerate(steps):
        logger.info("[LOOP] Step %d/%d: tool=%s purpose=%s", step_idx+1, len(steps), step.tool, step.purpose)

        if step.is_direct_response:
            # No tool execution needed — record and move on
            records.append(StepRecord(
                step_index=step_idx, attempt=0, tool="respond_directly",
                params={}, purpose=step.purpose,
                result={"success": True, "message": step.response_text or ""},
                reflect=ReflectResult(success=True, reason="Direct response, no execution needed"),
            ))
            continue

        current_step = step
        attempt = 0
        step_succeeded = False

        while attempt < max_retries:
            # ── EXECUTE ───────────────────────────────────────────────────
            emit_event_fn("TOOL_EXECUTION", {
                "phase": "execute",
                "stepIndex": step_idx,
                "attempt": attempt,
                "tool": current_step.tool,
                "params": current_step.params,
                "purpose": current_step.purpose,
            })
            logger.info("[LOOP] EXECUTE step=%d attempt=%d tool=%s", step_idx, attempt, current_step.tool)

            result = execute_fn(current_step.tool, current_step.params)
            logger.info("[LOOP] EXECUTE result: success=%s msg=%s", result.get("success"), result.get("message", "")[:80])

            # ── Confirmation gate ─────────────────────────────────────────
            if result.get("requires_confirmation"):
                action_id = result.get("action_id", "")
                logger.info("[LOOP] Step %d requires confirmation — pausing loop", step_idx)
                remaining = steps[step_idx:]   # re-execute from current step after confirm
                raise ConfirmationRequired(action_id, remaining, records)

            # ── REFLECT ───────────────────────────────────────────────────
            emit_event_fn("THINKING", {
                "phase": "reflect",
                "stepIndex": step_idx,
                "attempt": attempt,
            })
            reflect = run_reflect_phase(current_step, result, user_message, groq_client, model)
            logger.info("[LOOP] REFLECT step=%d attempt=%d success=%s reason=%s",
                        step_idx, attempt, reflect.success, reflect.reason[:80])

            records.append(StepRecord(
                step_index=step_idx, attempt=attempt,
                tool=current_step.tool, params=current_step.params,
                purpose=current_step.purpose, result=result, reflect=reflect,
            ))

            if reflect.success:
                step_succeeded = True
                break

            # ── RETRY ─────────────────────────────────────────────────────
            attempt += 1
            total_retries += 1
            if reflect.revised_step and attempt < max_retries:
                logger.info("[LOOP] RETRY step=%d with revised tool=%s", step_idx, reflect.revised_step.tool)
                current_step = reflect.revised_step
                emit_event_fn("THINKING", {
                    "phase": "retry",
                    "stepIndex": step_idx,
                    "attempt": attempt,
                    "reason": reflect.reason,
                })
            else:
                # No revised step available, or retries exhausted
                break

        if not step_succeeded:
            any_exhausted = True
            last_reason = records[-1].reflect.reason if records and records[-1].reflect else "unknown error"
            logger.warning("[LOOP] Step %d exhausted retries. Last reason: %s", step_idx, last_reason)
            # Stop processing further steps — narrate failure
            summary_text = _narrate_exhaustion(user_message, last_reason, groq_client, model)
            emit_event_fn("ERROR", {
                "phase": "exhausted",
                "stepIndex": step_idx,
                "totalRetries": total_retries,
                "reason": last_reason,
            })
            return AgentLoopResult(
                summary_text=summary_text,
                steps_executed=records,
                total_retries=total_retries,
                exhausted=True,
            )

    # ── All steps succeeded ───────────────────────────────────────────────────
    summary_text = _narrate_completion(user_message, records, groq_client, model)
    emit_event_fn("SUCCESS", {
        "phase": "done",
        "stepsCompleted": len(steps),
        "totalRetries": total_retries,
    })
    logger.info("[LOOP] DONE — %d steps, %d retries, exhausted=%s", len(steps), total_retries, any_exhausted)

    return AgentLoopResult(
        summary_text=summary_text,
        steps_executed=records,
        total_retries=total_retries,
        exhausted=False,
    )
