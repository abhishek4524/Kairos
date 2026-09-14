"""
permissions.py — Security Permission Engine, 4-Tier Risk Model & Injection Guard for Kairos.

4-Tier Risk Hierarchy:
  1. SAFE                  — Read-only tools, app launches, web navigation (Run immediately).
  2. CONFIRM_ONCE          — Workspace file edits, sandbox code running (Can remember for session).
  3. CONFIRM_EVERY_TIME    — File deletion, outbound emails/messages, git push (Always confirm).
  4. DANGEROUS             — Shell commands with admin rights (Requires exact typed phrase).
  *. BLOCKED               — Credential dumping, private keys, financial payments (Permanently blocked).
"""

import enum
import os
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from agent_tools import audit_logger
from agent_tools import protected_zone

# ── Workspace Directory Configuration ─────────────────────────────────────────
DEFAULT_WORKSPACE = os.path.expanduser(os.environ.get("KAIROS_WORKSPACE_DIR", "~/KairosWorkspace"))
TRASH_DIR = os.path.join(DEFAULT_WORKSPACE, ".trash")


def ensure_workspace_dirs():
    try:
        os.makedirs(DEFAULT_WORKSPACE, exist_ok=True)
        os.makedirs(TRASH_DIR, exist_ok=True)
    except Exception as e:
        print(f"[Permissions] Failed to create workspace/trash directories: {e}")


ensure_workspace_dirs()

# ── Security Mode ─────────────────────────────────────────────────────────────
SECURITY_MODE = os.environ.get("KAIROS_SECURITY_MODE", "strict").lower().strip()
IS_TRUSTED_MODE = SECURITY_MODE == "trusted"


# ── Risk Tiers ────────────────────────────────────────────────────────────────

class RiskTier(str, enum.Enum):
    SAFE = "SAFE"
    CONFIRM_ONCE = "CONFIRM_ONCE"
    CONFIRM_EVERY_TIME = "CONFIRM_EVERY_TIME"
    DANGEROUS = "DANGEROUS"
    BLOCKED = "BLOCKED"


# Explicit tool tier mappings
TOOL_RISK_MAP: Dict[str, RiskTier] = {
    # Safe Tiers
    "get_current_datetime": RiskTier.SAFE,
    "get_weather": RiskTier.SAFE,
    "get_news": RiskTier.SAFE,
    "answer_general_question": RiskTier.SAFE,
    "web_search": RiskTier.SAFE,
    "search_web": RiskTier.SAFE,
    "google_search": RiskTier.SAFE,
    "query_spreadsheet": RiskTier.SAFE,
    "open_app": RiskTier.SAFE,
    "app_control": RiskTier.SAFE,
    "open_brave": RiskTier.SAFE,
    "open_vscode": RiskTier.SAFE,
    "close_app": RiskTier.SAFE,
    "open_youtube_in_brave": RiskTier.SAFE,
    "youtube_search": RiskTier.SAFE,
    "youtube_play_video": RiskTier.SAFE,
    "youtube_control": RiskTier.SAFE,
    "youtube_like_video": RiskTier.SAFE,
    "youtube_subscribe": RiskTier.SAFE,
    "search_and_play_youtube": RiskTier.SAFE,
    "open_github": RiskTier.SAFE,
    "open_instagram": RiskTier.SAFE,
    "instagram_action": RiskTier.SAFE,
    "navigate_to": RiskTier.SAFE,
    "scroll_page": RiskTier.SAFE,
    "extract_page_text": RiskTier.SAFE,
    "read_page": RiskTier.SAFE,
    "go_back": RiskTier.SAFE,
    "open_new_tab": RiskTier.SAFE,
    "switch_tab": RiskTier.SAFE,
    "work_mode": RiskTier.SAFE,
    "check_whatsapp_notifications": RiskTier.SAFE,
    "get_project_context": RiskTier.SAFE,
    "query_codebase": RiskTier.SAFE,
    "explain_git_diff": RiskTier.SAFE,
    "explain_error": RiskTier.SAFE,
    "activate_focus_mode": RiskTier.SAFE,
    "activate_hackathon_mode": RiskTier.SAFE,
    # UI automation — transient, interactive, no persistent side-effects
    "find_and_click": RiskTier.SAFE,
    "type_into": RiskTier.SAFE,
    "cursor_control": RiskTier.SAFE,
    "type_in_active_window": RiskTier.SAFE,

    # File and Folder Management (Create, Rename, List)
    "create_folder": RiskTier.SAFE,
    "create_file": RiskTier.SAFE,
    "rename_file_or_folder": RiskTier.SAFE,
    "list_directory_contents": RiskTier.SAFE,

    # Camera Gesture Control
    "start_camera_gesture_control": RiskTier.SAFE,
    "stop_camera_gesture_control": RiskTier.SAFE,
    "get_camera_gesture_status": RiskTier.SAFE,
    "set_camera_gesture_mode": RiskTier.SAFE,

    # Command Execution & Terminal Aliases
    "open_cmd": RiskTier.SAFE,
    "run_cmd": RiskTier.SAFE,
    "run_command": RiskTier.SAFE,
    "exec_cmd": RiskTier.SAFE,
    "execute_command": RiskTier.SAFE,
    "propose_terminal_command": RiskTier.SAFE,

    # Confirm Once (code execution / disk writes)
    "open_notepad_and_write_code": RiskTier.CONFIRM_ONCE,
    "open_vscode_and_write_code": RiskTier.CONFIRM_ONCE,
    "write_and_run_sandbox_code": RiskTier.CONFIRM_ONCE,
    "run_terminal_command": RiskTier.CONFIRM_ONCE,
    "apply_code_patch": RiskTier.CONFIRM_ONCE,

    # Confirm Every Time (Destructive & Communication)
    "delete_file": RiskTier.CONFIRM_EVERY_TIME,
    "send_whatsapp_message": RiskTier.CONFIRM_EVERY_TIME,
    "send_whatsapp_desktop_message": RiskTier.SAFE,
    "open_whatsapp_chat": RiskTier.SAFE,
    "send_email": RiskTier.CONFIRM_EVERY_TIME,
    "send_sms": RiskTier.CONFIRM_EVERY_TIME,
    "post_tweet": RiskTier.CONFIRM_EVERY_TIME,
    "git_commit_and_push": RiskTier.CONFIRM_EVERY_TIME,
}

# Backward-compat alias: set of all explicitly registered tool names
PERMITTED_TOOLS = set(TOOL_RISK_MAP.keys())

# ── Hard Block Non-Path-Based Rules (Credentials / Financial) ─────────────────
FINANCIAL_PATTERNS = [
    r"\bpay\s+now\b",
    r"\bmake\s+payment\b",
    r"\bcomplete\s+order\b",
    r"\bcredit\s+card\b",
    r"\bcvv\b",
    r"\botp\b",
    r"\btransfer\s+money\b",
    r"\bbank\s+account\b",
    r"\bcheckout\s+and\s+pay\b",
]
_FINANCIAL_RE = re.compile("|".join(FINANCIAL_PATTERNS), re.IGNORECASE)

CREDENTIAL_PATTERNS = [
    r"\b(id_rsa|id_ecdsa|id_ed25519)\b",
    r"\.pem\b",
    r"\.key\b",
    r"\.env\b",
    r"\bshadow\b",
    r"\bsam\b",
    r"\bmimikatz\b",
    r"\bpasswords?\.(txt|json|db)\b",
    r"\bdump\s+credentials\b",
]
_CREDENTIAL_RE = re.compile("|".join(CREDENTIAL_PATTERNS), re.IGNORECASE)

DANGEROUS_SHELL_PATTERNS = [
    r"\bformat\s+[a-z]:",
    r"\bdiskpart\b",
    r"\breg\s+add\b",
    r"\breg\s+delete\b",
    r"\bnetsh\b",
    r"\bpowershell\s+-enc\b",
    r"\bInvoke-Expression\b",
    r"\biex\b",
    r"\bchmod\s+777\b",
    r"\brm\s+-rf\s+/(?:\s|$)",
]
_DANGEROUS_SHELL_RE = re.compile("|".join(DANGEROUS_SHELL_PATTERNS), re.IGNORECASE)


# ── Untrusted Data Tagging & Prompt Injection Defense ─────────────────────────

def tag_untrusted_data(content: str, source: str = "webpage") -> str:
    """
    Encloses untrusted external content (web pages, user documents, tool results)
    in structured DATA tags to prevent LLM prompt injection and instruction blending.
    """
    if not content:
        return ""
    sanitized = content.replace("</UNTRUSTED_DATA>", "[TAG_ESCAPED]")
    return f'<UNTRUSTED_DATA source="{source}">\n{sanitized}\n</UNTRUSTED_DATA>'


def detect_prompt_injection(content: str) -> Tuple[bool, str]:
    """
    Heuristic scanner for adversarial instruction patterns inside untrusted data.
    """
    if not content:
        return False, ""
    injection_patterns = [
        (r"ignore\s+(?:all\s+)?previous\s+instructions", "Instruction override pattern"),
        (r"you\s+are\s+now\s+in\s+developer\s+mode", "Jailbreak pattern"),
        (r"system\s*prompt\s*:", "System prompt spoofing"),
        (r"send\s+all\s+files\s+to", "Exfiltration pattern"),
        (r"upload\s+(?:passwords|\.env|credentials)", "Credential theft pattern"),
    ]
    for pattern, name in injection_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            return True, f"Matched injection rule: {name}"
    return False, ""


# ── Pending Confirmation State Manager ─────────────────────────────────────────

@dataclass
class PendingAction:
    action_id: str
    action_type: str
    tool_name: str
    params: Dict[str, Any]
    target_summary: str
    confirmation_prompt: str
    risk_tier: RiskTier = RiskTier.CONFIRM_EVERY_TIME
    required_typed_phrase: Optional[str] = None
    session_key: Optional[str] = None
    source_origin: str = "user_command"
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 90.0)


class ConfirmationManager:
    """Manages multi-tier confirmations, session approvals, and typed confirmation requirements."""

    def __init__(self):
        self._pending: Dict[str, PendingAction] = {}
        self._session_approved: Set[str] = set()

    def is_session_approved(self, session_key: str) -> bool:
        return session_key in self._session_approved

    def approve_for_session(self, session_key: str) -> None:
        if session_key:
            self._session_approved.add(session_key)

    def register_pending(
        self,
        action_type: str,
        tool_name: str,
        params: Dict[str, Any],
        target_summary: str,
        confirmation_prompt: str,
        risk_tier: RiskTier = RiskTier.CONFIRM_EVERY_TIME,
        required_phrase: Optional[str] = None,
        session_key: Optional[str] = None,
        source_origin: str = "user_command",
    ) -> PendingAction:
        action_id = str(uuid.uuid4())[:8]
        pending = PendingAction(
            action_id=action_id,
            action_type=action_type,
            tool_name=tool_name,
            params=params,
            target_summary=target_summary,
            confirmation_prompt=confirmation_prompt,
            risk_tier=risk_tier,
            required_typed_phrase=required_phrase,
            session_key=session_key,
            source_origin=source_origin,
        )
        self._pending[action_id] = pending

        audit_logger.log_event(
            event_type=f"{action_type}_PENDING",
            tool_name=tool_name,
            target=target_summary,
            outcome="AWAITING_CONFIRMATION",
            details={
                "action_id": action_id,
                "tier": risk_tier.value,
                "required_phrase": required_phrase,
                "source_origin": source_origin,
            },
        )
        return pending

    def validate_confirmation(
        self, action_id: str, confirmation_text: str, remember_session: bool = False
    ) -> Tuple[bool, Optional[PendingAction], str]:
        pending = self._pending.get(action_id)
        if not pending:
            return False, None, "No active pending action found for this ID (it may have expired)."

        if time.time() > pending.expires_at:
            del self._pending[action_id]
            audit_logger.log_event(
                event_type=f"{pending.action_type}_EXPIRED",
                tool_name=pending.tool_name,
                target=pending.target_summary,
                outcome="EXPIRED",
                details={"action_id": action_id},
            )
            return False, None, "The confirmation request has expired (90s limit). Please re-initiate the action."

        text = confirmation_text.strip()

        # Tier 4: Dangerous requires exact typed phrase match
        if pending.risk_tier == RiskTier.DANGEROUS and pending.required_typed_phrase:
            if text != pending.required_typed_phrase:
                return (
                    False,
                    None,
                    f"Dangerous action requires exact typed confirmation phrase: '{pending.required_typed_phrase}'",
                )

        # Affirmative tokens for standard tiers
        affirmative = {
            "yes", "confirm", "proceed", "send it", "do it", "sure", "confirmed",
            "delete it", "go ahead", "yes please", "yes confirm", "approve"
        }
        negative = {"no", "cancel", "stop", "abort", "don't", "dont", "never mind", "nevermind", "wait", "decline"}

        if pending.risk_tier == RiskTier.DANGEROUS and text == pending.required_typed_phrase:
            del self._pending[action_id]
            audit_logger.log_event(
                event_type=f"{pending.action_type}_CONFIRMED",
                tool_name=pending.tool_name,
                target=pending.target_summary,
                outcome="USER_TYPED_CONFIRMED",
                details={"action_id": action_id, "tier": pending.risk_tier.value},
            )
            return True, pending, "Dangerous action confirmed via typed phrase."

        if text.lower() in affirmative or any(text.lower() == a for a in affirmative):
            del self._pending[action_id]
            if remember_session and pending.session_key:
                self.approve_for_session(pending.session_key)

            audit_logger.log_event(
                event_type=f"{pending.action_type}_CONFIRMED",
                tool_name=pending.tool_name,
                target=pending.target_summary,
                outcome="USER_CONFIRMED",
                details={"action_id": action_id, "remember_session": remember_session},
            )
            return True, pending, "Action confirmed by user."

        elif text.lower() in negative or any(text.lower() == n for n in negative):
            del self._pending[action_id]
            audit_logger.log_event(
                event_type=f"{pending.action_type}_CANCELLED",
                tool_name=pending.tool_name,
                target=pending.target_summary,
                outcome="USER_CANCELLED",
                details={"action_id": action_id, "reply": text},
            )
            return False, None, f"Action cancelled by user (received '{text}')."

        else:
            return False, None, f"Ambiguous reply '{text}' received. Confirmation must be an explicit 'yes' or 'confirm'."


confirmation_mgr = ConfirmationManager()


# ── Risk Assessment Engine ───────────────────────────────────────────────────

def evaluate_risk(
    tool_name: str,
    params: Dict[str, Any],
    source_origin: str = "user_command",
) -> Tuple[RiskTier, str, Optional[str]]:
    """
    Evaluates the risk tier for a tool execution attempt.
    Returns (RiskTier, reason, optional_required_typed_phrase).
    """
    # 1. Hard Block: Check for financial/credential keywords
    params_str = " ".join(str(v) for v in params.values())
    if _FINANCIAL_RE.search(params_str) or _FINANCIAL_RE.search(tool_name):
        return RiskTier.BLOCKED, "Financial/payment actions are permanently blocked.", None

    if _CREDENTIAL_RE.search(params_str):
        return RiskTier.BLOCKED, "Credential/key extraction is permanently blocked.", None

    # 2. Check for dangerous shell commands
    if tool_name in ("run_terminal_command", "write_and_run_sandbox_code"):
        cmd_text = str(params.get("command", "") or params.get("code", ""))
        if _DANGEROUS_SHELL_RE.search(cmd_text):
            return (
                RiskTier.DANGEROUS,
                "Dangerous system modification command detected.",
                "I CONFIRM DANGEROUS SYSTEM COMMAND",
            )

    # 3. Lookup base tier
    tier = TOOL_RISK_MAP.get(tool_name, RiskTier.CONFIRM_EVERY_TIME)

    # 4. Check workspace containment for file edits
    if tool_name in ("open_notepad_and_write_code", "open_vscode_and_write_code", "write_and_run_sandbox_code"):
        fn = str(params.get("filename", ""))
        if fn:
            is_valid, _, err = resolve_secure_workspace_path(fn)
            if not is_valid:
                return RiskTier.BLOCKED, f"Path security violation: {err}", None

    return tier, f"Standard risk tier for {tool_name}", None


# ── Secure Workspace Path Containment ─────────────────────────────────────────

def resolve_secure_workspace_path(filename_or_path: str) -> Tuple[bool, str, str]:
    if not filename_or_path:
        return False, "", "No filename or path specified."

    clean = filename_or_path.strip()
    if not os.path.isabs(clean) and not clean.startswith("~"):
        target_path = os.path.abspath(os.path.join(DEFAULT_WORKSPACE, clean))
    else:
        target_path = os.path.abspath(os.path.expanduser(clean))

    norm_workspace = os.path.normcase(os.path.abspath(DEFAULT_WORKSPACE))
    norm_target = os.path.normcase(target_path)

    if not (norm_target == norm_workspace or norm_target.startswith(norm_workspace + os.sep)):
        return (
            False,
            target_path,
            f"Access denied: Target '{clean}' is outside allowed workspace directory ({DEFAULT_WORKSPACE}).",
        )

    return True, target_path, ""


def safe_delete_file(target_file_path: str) -> Tuple[bool, str, str]:
    is_valid, resolved_path, err_msg = resolve_secure_workspace_path(target_file_path)
    if not is_valid:
        return False, "", err_msg

    if not os.path.exists(resolved_path):
        return False, resolved_path, f"File does not exist: '{target_file_path}'"

    try:
        ensure_workspace_dirs()
        fname = os.path.basename(resolved_path)
        trash_dest = os.path.join(TRASH_DIR, f"{int(time.time())}_{fname}")
        shutil.move(resolved_path, trash_dest)

        audit_logger.log_event(
            event_type="FILE_DELETED",
            tool_name="delete_file",
            target=resolved_path,
            outcome="MOVED_TO_TRASH",
            details={"trash_path": trash_dest},
        )
        return True, trash_dest, f"File safely moved to trash: {os.path.basename(trash_dest)}"
    except Exception as e:
        return False, resolved_path, f"Failed to move file to trash: {e}"


# ── move_to_trash backward-compat alias ───────────────────────────────────────

def move_to_trash(file_path: str) -> Tuple[bool, str]:
    """Backward-compat alias for safe_delete_file. Returns (ok, message)."""
    ok, _trash, msg = safe_delete_file(file_path)
    return ok, msg


# ── Backward-Compat validate_tool_call (used by executor.py) ─────────────────

_COMMUNICATION_TOOLS = {
    "send_whatsapp_message",
    "send_email", "send_sms", "post_tweet",
}


def validate_tool_call(
    tool_name: str,
    params: Dict[str, Any],
    confirmed_action_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Gate function called by executor.py before each tool execution.
    Applies 4-tier risk evaluation; blocks or queues confirmation as required.
    Completes immediately for SAFE / already-confirmed tools.
    """
    # ── 1. Unknown tool check ─────────────────────────────────────────────────
    if tool_name not in TOOL_RISK_MAP:
        audit_logger.log_event(
            event_type="UNKNOWN_TOOL_BLOCKED",
            tool_name=tool_name,
            target=str(params),
            outcome="BLOCKED",
            details={"reason": "not in allowlist"},
        )
        return {
            "permitted": False,
            "error_type": "PERMISSION_DENIED",
            "message": f"Tool '{tool_name}' is not in the Kairos permitted tools allowlist.",
            "safe_params": params,
        }

    # ── 2. Already confirmed by action ID: bypass further checks ─────────────
    if confirmed_action_id:
        return {"permitted": True, "safe_params": params, "tier": TOOL_RISK_MAP[tool_name].value}

    # ── 3. Workspace path containment check ──────────────────────────────────
    path_param_keys = ["filename", "filepath", "path", "file", "dest", "destination", "target"]
    for pk in path_param_keys:
        val = params.get(pk)
        if isinstance(val, str) and val.strip():
            is_valid, _, err = resolve_secure_workspace_path(val)
            if not is_valid:
                audit_logger.log_event(
                    event_type="WORKSPACE_VIOLATION",
                    tool_name=tool_name,
                    target=val,
                    outcome="BLOCKED",
                    details={"param_key": pk, "reason": err},
                )
                return {
                    "permitted": False,
                    "error_type": "WORKSPACE_VIOLATION",
                    "message": err,
                    "security_alert": True,
                    "safe_params": params,
                }

    # ── 4. Shell injection check ──────────────────────────────────────────────
    if tool_name in ("run_terminal_command", "write_and_run_sandbox_code"):
        cmd_text = str(params.get("command", "") or params.get("code", ""))
        if _DANGEROUS_SHELL_RE.search(cmd_text):
            audit_logger.log_event(
                event_type="SHELL_INJECTION_BLOCKED",
                tool_name=tool_name,
                target=cmd_text[:80],
                outcome="BLOCKED",
                details={"reason": "dangerous shell pattern matched"},
            )
            return {
                "permitted": False,
                "error_type": "SHELL_INJECTION_DETECTED",
                "message": "Dangerous shell command pattern detected and blocked.",
                "security_alert": True,
                "safe_params": params,
            }

    # ── 5. Protected zone check ───────────────────────────────────────────────
    is_blocked, block_reason = protected_zone.check_protected_zone(tool_name, params)
    if is_blocked:
        return {
            "permitted": False,
            "error_type": "PROTECTED_ZONE_BLOCKED",
            "message": block_reason,
            "security_alert": True,
            "safe_params": params,
        }

    # ── 6. Financial/credential hard block ────────────────────────────────────
    params_str = " ".join(str(v) for v in params.values())
    if _FINANCIAL_RE.search(params_str) or _FINANCIAL_RE.search(tool_name):
        return {
            "permitted": False,
            "error_type": "PERMANENTLY_BLOCKED",
            "message": "Financial/payment actions are permanently blocked.",
            "security_alert": True,
            "safe_params": params,
        }
    if _CREDENTIAL_RE.search(params_str):
        return {
            "permitted": False,
            "error_type": "PERMANENTLY_BLOCKED",
            "message": "Credential/key extraction is permanently blocked.",
            "security_alert": True,
            "safe_params": params,
        }

    tier = TOOL_RISK_MAP.get(tool_name, RiskTier.CONFIRM_EVERY_TIME)

    # ── 7. SAFE tier: run immediately ────────────────────────────────────────
    if tier == RiskTier.SAFE:
        return {"permitted": True, "safe_params": params, "tier": tier.value}

    # ── 8. Communication tools: validate recipient & confirm ─────────────────
    if tool_name in _COMMUNICATION_TOOLS:
        recipient = (params.get("recipient") or params.get("contact_name") or params.get("contact") or "").strip()
        if not recipient:
            return {
                "permitted": False,
                "error_type": "AMBIGUOUS_RECIPIENT",
                "message": "Recipient is missing or ambiguous. Please specify a clear recipient.",
                "safe_params": params,
            }
        # Requires confirmation every time
        target_summary = f"Send to {recipient}: {str(params.get('message', ''))[:60]}"
        prompt = f"Send message to '{recipient}'? Reply 'yes' or 'send it' to confirm."
        pending = confirmation_mgr.register_pending(
            action_type="COMMUNICATION",
            tool_name=tool_name,
            params=params,
            target_summary=target_summary,
            confirmation_prompt=prompt,
            risk_tier=RiskTier.CONFIRM_EVERY_TIME,
        )
        return {
            "permitted": False,
            "requires_confirmation": True,
            "confirmation_type": "COMMUNICATION",
            "action_id": pending.action_id,
            "confirmation_prompt": prompt,
            "message": prompt,
            "target_summary": target_summary,
            "safe_params": params,
        }

    # ── 9. CONFIRM_ONCE: check session approval ───────────────────────────────
    if tier == RiskTier.CONFIRM_ONCE:
        session_key = f"{tool_name}_session"
        if confirmation_mgr.is_session_approved(session_key):
            return {"permitted": True, "safe_params": params, "tier": tier.value}

    # ── 10. DANGEROUS tier ────────────────────────────────────────────────────
    if tier == RiskTier.DANGEROUS:
        required_phrase = "I CONFIRM DANGEROUS SYSTEM COMMAND"
        target_summary = str(params.get("command", params.get("code", tool_name)))[:100]
        prompt_text = f"⚠️ DANGEROUS: Type exactly '{required_phrase}' to proceed."
        pending = confirmation_mgr.register_pending(
            action_type="DANGEROUS",
            tool_name=tool_name,
            params=params,
            target_summary=target_summary,
            confirmation_prompt=prompt_text,
            risk_tier=tier,
            required_phrase=required_phrase,
        )
        return {
            "permitted": False,
            "requires_confirmation": True,
            "confirmation_type": "DANGEROUS",
            "action_id": pending.action_id,
            "confirmation_prompt": prompt_text,
            "message": f"Dangerous action requires typed confirmation: '{required_phrase}'",
            "target_summary": target_summary,
            "safe_params": params,
        }

    # ── 11. CONFIRM_ONCE or CONFIRM_EVERY_TIME: queue standard confirmation ───
    target_summary = str(params)[:120]
    action_type = "DESTRUCTIVE" if tier == RiskTier.CONFIRM_EVERY_TIME else "SANDBOX"
    prompt = f"Shall I proceed with {tool_name}? Reply 'yes' to confirm or 'no' to cancel."
    pending = confirmation_mgr.register_pending(
        action_type=action_type,
        tool_name=tool_name,
        params=params,
        target_summary=target_summary,
        confirmation_prompt=prompt,
        risk_tier=tier,
    )
    return {
        "permitted": False,
        "requires_confirmation": True,
        "confirmation_type": action_type,
        "action_id": pending.action_id,
        "confirmation_prompt": prompt,
        "message": f"Please confirm: {prompt}",
        "target_summary": target_summary,
        "safe_params": params,
    }

