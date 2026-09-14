"""
task_planner.py — Plan/Preview/Approve Lifecycle & Honest Failure Reporting for Kairos.

Phases:
  1. PLAN       — Decompose user request into ordered structured steps with risk tiers.
  2. PREVIEW    — Present plan to frontend with risk badge; wait for approval / edit.
  3. APPROVE    — User approves / edits (removes or reorders steps).
  4. EXECUTE    — Run approved steps sequentially with live progress telemetry.
  5. VERIFY     — Validate each step's output (detect partial failures / uncertainty).
  6. REPORT     — Deliver an honest report clearly separating succeeded vs failed steps with recovery options.
"""

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent_tools import audit_logger
from agent_tools.permissions import RiskTier, evaluate_risk

logger = logging.getLogger("kairos.task_planner")


@dataclass
class PlannedStep:
    step_id: int
    tool: str
    params: Dict[str, Any]
    description: str
    risk_tier: RiskTier = RiskTier.SAFE
    status: str = "pending"  # "pending", "running", "succeeded", "failed", "uncertain", "skipped"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    recovery_action: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "tool": self.tool,
            "params": self.params,
            "description": self.description,
            "risk_tier": self.risk_tier.value,
            "status": self.status,
            "error": self.error,
            "recovery_action": self.recovery_action,
        }


@dataclass
class TaskPlan:
    plan_id: str
    user_request: str
    steps: List[PlannedStep]
    highest_risk_tier: RiskTier = RiskTier.SAFE
    risk_score: int = 1  # 1 (Safe) to 4 (Dangerous)
    requires_preview: bool = True
    approved: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "user_request": self.user_request,
            "steps": [s.to_dict() for s in self.steps],
            "highest_risk_tier": self.highest_risk_tier.value,
            "risk_score": self.risk_score,
            "requires_preview": self.requires_preview,
            "approved": self.approved,
            "step_count": len(self.steps),
        }


# ── Active Plan Registry for Frontend Approval ────────────────────────────────
_ACTIVE_PLANS: Dict[str, TaskPlan] = {}


def get_plan(plan_id: str) -> Optional[TaskPlan]:
    return _ACTIVE_PLANS.get(plan_id)


def remove_step_from_plan(plan_id: str, step_id: int) -> Optional[TaskPlan]:
    plan = _ACTIVE_PLANS.get(plan_id)
    if not plan:
        return None
    plan.steps = [s for s in plan.steps if s.step_id != step_id]
    # Recompute risk
    _recalculate_plan_risk(plan)
    return plan


def _recalculate_plan_risk(plan: TaskPlan) -> None:
    tier_weights = {
        RiskTier.SAFE: 1,
        RiskTier.CONFIRM_ONCE: 2,
        RiskTier.CONFIRM_EVERY_TIME: 3,
        RiskTier.DANGEROUS: 4,
        RiskTier.BLOCKED: 5,
    }
    max_weight = 1
    max_tier = RiskTier.SAFE
    for step in plan.steps:
        tier, _, _ = evaluate_risk(step.tool, step.params)
        step.risk_tier = tier
        w = tier_weights.get(tier, 1)
        if w > max_weight:
            max_weight = w
            max_tier = tier

    plan.highest_risk_tier = max_tier
    plan.risk_score = min(max_weight, 4)
    # Fast path rule: single safe deterministic step does not require full preview ceremony
    if len(plan.steps) <= 1 and max_tier == RiskTier.SAFE:
        plan.requires_preview = False
    else:
        plan.requires_preview = True


def create_plan_from_steps(user_request: str, raw_steps: List[Dict[str, Any]]) -> TaskPlan:
    plan_id = str(uuid.uuid4())[:8]
    steps: List[PlannedStep] = []

    for idx, item in enumerate(raw_steps, start=1):
        tool = item.get("tool", "respond_directly")
        params = item.get("params", {})
        desc = item.get("description") or item.get("summary") or item.get("purpose") or f"Execute {tool}"
        tier, _, _ = evaluate_risk(tool, params)
        steps.append(PlannedStep(
            step_id=idx,
            tool=tool,
            params=params,
            description=desc,
            risk_tier=tier,
        ))

    plan = TaskPlan(
        plan_id=plan_id,
        user_request=user_request,
        steps=steps,
    )
    _recalculate_plan_risk(plan)
    _ACTIVE_PLANS[plan_id] = plan
    return plan


def execute_plan_sync(
    plan: TaskPlan,
    execute_fn: Callable[[str, Dict[str, Any]], Dict[str, Any]],
    emit_event_fn: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
) -> Dict[str, Any]:
    """
    Sequentially executes each step of an approved plan.
    Records honest outcomes and produces a structured final report.
    """
    if emit_event_fn is None:
        emit_event_fn = lambda ev, pl: None

    plan.approved = True
    audit_logger.log_event(
        event_type="PLAN_EXECUTION_STARTED",
        tool_name="task_planner",
        target=plan.plan_id,
        outcome="RUNNING",
        details={"plan_id": plan.plan_id, "step_count": len(plan.steps)},
    )

    succeeded_steps = []
    failed_steps = []
    uncertain_steps = []

    for step in plan.steps:
        step.status = "running"
        emit_event_fn("PLAN_STEP_STARTED", {
            "plan_id": plan.plan_id,
            "step_id": step.step_id,
            "description": step.description,
            "tool": step.tool,
        })

        t0 = time.time()
        try:
            res = execute_fn(step.tool, step.params)
            step.result = res
            dt = round((time.time() - t0) * 1000, 1)

            # Check outcome honesty
            if res.get("success") is True:
                step.status = "succeeded"
                succeeded_steps.append(step)
                emit_event_fn("PLAN_STEP_COMPLETED", {
                    "plan_id": plan.plan_id,
                    "step_id": step.step_id,
                    "status": "succeeded",
                    "latency_ms": dt,
                })
            elif res.get("uncertain") is True:
                step.status = "uncertain"
                step.error = res.get("message", "Result outcome could not be verified with high confidence.")
                step.recovery_action = f"Verify {step.tool} status manually."
                uncertain_steps.append(step)
                emit_event_fn("PLAN_STEP_COMPLETED", {
                    "plan_id": plan.plan_id,
                    "step_id": step.step_id,
                    "status": "uncertain",
                    "error": step.error,
                })
            else:
                step.status = "failed"
                step.error = res.get("message") or res.get("error") or "Execution returned failure code."
                step.recovery_action = f"Retry {step.tool}" if "network" in str(step.error).lower() else f"Open {step.tool} manually"
                failed_steps.append(step)
                emit_event_fn("PLAN_STEP_COMPLETED", {
                    "plan_id": plan.plan_id,
                    "step_id": step.step_id,
                    "status": "failed",
                    "error": step.error,
                    "recovery_action": step.recovery_action,
                })

        except Exception as exc:
            step.status = "failed"
            step.error = str(exc)
            step.recovery_action = f"Retry step {step.step_id}"
            failed_steps.append(step)
            emit_event_fn("PLAN_STEP_COMPLETED", {
                "plan_id": plan.plan_id,
                "step_id": step.step_id,
                "status": "failed",
                "error": str(exc),
            })

    # Produce Honest Report
    report = format_honest_report(plan)
    all_succeeded = len(failed_steps) == 0 and len(uncertain_steps) == 0

    audit_logger.log_event(
        event_type="PLAN_EXECUTION_FINISHED",
        tool_name="task_planner",
        target=plan.plan_id,
        outcome="SUCCESS" if all_succeeded else "PARTIAL_FAILURE",
        details={
            "succeeded": len(succeeded_steps),
            "failed": len(failed_steps),
            "uncertain": len(uncertain_steps),
        },
    )

    return {
        "plan_id": plan.plan_id,
        "all_succeeded": all_succeeded,
        "succeeded_count": len(succeeded_steps),
        "failed_count": len(failed_steps),
        "uncertain_count": len(uncertain_steps),
        "report": report,
        "steps": [s.to_dict() for s in plan.steps],
    }


def format_honest_report(plan: TaskPlan) -> str:
    """
    Constructs an explicit, truthful summary of plan execution separating
    succeeded, failed, and uncertain steps with recovery suggestions.
    """
    lines = []
    lines.append(f"### Plan Execution Summary (Plan #{plan.plan_id})")
    lines.append("")

    succeeded = [s for s in plan.steps if s.status == "succeeded"]
    failed = [s for s in plan.steps if s.status == "failed"]
    uncertain = [s for s in plan.steps if s.status == "uncertain"]

    if succeeded:
        lines.append("**Completed Successfully:**")
        for s in succeeded:
            lines.append(f"  ✓ Step {s.step_id}: {s.description}")
        lines.append("")

    if failed:
        lines.append("**Failed Steps:**")
        for s in failed:
            lines.append(f"  ✗ Step {s.step_id}: {s.description}")
            lines.append(f"    - Reason: {s.error}")
            if s.recovery_action:
                lines.append(f"    - Suggested Recovery: {s.recovery_action}")
        lines.append("")

    if uncertain:
        lines.append("**Uncertain Outcome (Needs Verification):**")
        for s in uncertain:
            lines.append(f"  ? Step {s.step_id}: {s.description} ({s.error})")
        lines.append("")

    if not failed and not uncertain:
        lines.append("All steps completed successfully.")
    elif failed and succeeded:
        lines.append("Note: The task completed partially. You can retry the failed steps above or proceed manually.")

    return "\n".join(lines)
