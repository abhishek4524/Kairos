"""
permissions.py — Security Permission Engine & Confirmation Guard for Kairos.

Enforces:
1. Tool Execution Allowlist & Per-Tool Parameter Constraints.
2. Workspace directory containment (prevents path traversal outside ~/KairosWorkspace).
3. Command & metacharacter sanitization for sandbox executions.
4. Strict Mode vs. Trusted Mode execution levels.
5. Mandatory Two-Step Confirmation for destructive actions (file/data deletion, DB clear, etc.)
   with local trash/undo recovery.
6. Mandatory Two-Step Confirmation for outbound communications (WhatsApp, email, social posts)
   with readback and contact disambiguation.
"""

import os
import re
import time
import uuid
import shutil
from typing import Dict, Any, Optional, Tuple, Set, List
from dataclasses import dataclass, field

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

# ── Mode Configuration ────────────────────────────────────────────────────────
# Strict Mode (default) vs Trusted Mode
SECURITY_MODE = os.environ.get("KAIROS_SECURITY_MODE", "strict").lower().strip()
IS_TRUSTED_MODE = SECURITY_MODE == "trusted"


# ── Tool Execution Allowlist ──────────────────────────────────────────────────
# Explicit set of permitted tools matching registry.py
PERMITTED_TOOLS: Set[str] = {
    # Generic Browser Primitives
    "navigate_to",
    "find_and_click",
    "type_into",
    "scroll_page",
    "extract_page_text",
    "read_page",
    "go_back",
    "open_new_tab",
    "switch_tab",
    # Legacy YouTube Shortcuts
    "open_youtube_in_brave",
    "youtube_search",
    "youtube_play_video",
    "youtube_control",
    "search_and_play_youtube",
    # Desktop OS Tools
    "open_app",
    "open_brave",
    "open_vscode",
    "close_app",
    "cursor_control",
    "type_in_active_window",
    "open_notepad_and_write_code",
    "open_vscode_and_write_code",
    "write_and_run_sandbox_code",
    "work_mode",
    # Communication & Deletion Tools
    "check_whatsapp_notifications",
    "send_whatsapp_message",
    "send_whatsapp_desktop_message",
    "send_email",
    "delete_file",
    # Live Knowledge, News & Utility Tools (Read-Only)
    "get_current_datetime",
    "get_news",
    "answer_general_question",
}

# ── Sandbox Command Allowlist & Shell Metacharacter Regex ───────────────────────
STRICT_ALLOWED_COMMANDS = {"python", "node", "npm", "git", "echo", "ls", "dir", "cat", "type"}
SHELL_METACHARACTERS_REGEX = re.compile(r"[;&|`$<>\\\n\r]")


# ── Destructive Action Patterns ───────────────────────────────────────────────
DESTRUCTIVE_BROWSER_PATTERNS = [
    r"\bdelete\s+(account|profile|data|all)\b",
    r"\bcancel\s+order\b",
    r"\bunsubscribe\b",
    r"\bremove\s+(account|card|method)\b",
    r"\bwipe\s+(data|history)\b",
    r"\bclear\s+all\b",
]
_DESTRUCTIVE_BROWSER_RE = re.compile("|".join(DESTRUCTIVE_BROWSER_PATTERNS), re.IGNORECASE)

DESTRUCTIVE_COMMAND_PATTERNS = [
    r"\brm\s+-[rf]+",
    r"\bdel\s+/[fq]+",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[xfd]+",
    r"\bgit\s+push\s+.*--force",
    r"\bformat\s+[a-z]:",
    r"\bdrop\s+database\b",
    r"\btruncate\s+table\b",
]
_DESTRUCTIVE_CMD_RE = re.compile("|".join(DESTRUCTIVE_COMMAND_PATTERNS), re.IGNORECASE)


# ── Outbound Communication Patterns ────────────────────────────────────────────
COMMUNICATION_TOOLS = {"send_whatsapp_message", "send_whatsapp_desktop_message", "send_email", "send_sms", "post_tweet"}


# ── Pending Confirmation State Manager ─────────────────────────────────────────
@dataclass
class PendingAction:
    action_id: str
    action_type: str  # "DESTRUCTIVE" or "COMMUNICATION"
    tool_name: str
    params: Dict[str, Any]
    target_summary: str
    confirmation_prompt: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 90.0)


class ConfirmationManager:
    """Manages two-step confirmation flow state for destructive and communication actions."""
    def __init__(self):
        self._pending: Dict[str, PendingAction] = {}

    def register_pending(
        self,
        action_type: str,
        tool_name: str,
        params: Dict[str, Any],
        target_summary: str,
        confirmation_prompt: str
    ) -> PendingAction:
        action_id = str(uuid.uuid4())[:8]
        pending = PendingAction(
            action_id=action_id,
            action_type=action_type,
            tool_name=tool_name,
            params=params,
            target_summary=target_summary,
            confirmation_prompt=confirmation_prompt
        )
        self._pending[action_id] = pending
        
        # Log pending event
        audit_logger.log_event(
            event_type=f"{action_type}_PENDING",
            tool_name=tool_name,
            target=target_summary,
            outcome="AWAITING_CONFIRMATION",
            details={"action_id": action_id, "prompt": confirmation_prompt}
        )
        return pending

    def validate_confirmation(self, action_id: str, confirmation_text: str) -> Tuple[bool, Optional[PendingAction], str]:
        """
        Validates whether confirmation text is an explicit, unambiguous confirmation.
        Returns (is_confirmed: bool, pending_action: Optional[PendingAction], reason: str).
        """
        pending = self._pending.get(action_id)
        if not pending:
            return False, None, "No active pending action found for this ID (it may have expired)."

        if time.time() > pending.expires_at:
            del self._pending[action_id]
            audit_logger.log_event(
                event_type=f"{pending.action_type}_CANCELLED",
                tool_name=pending.tool_name,
                target=pending.target_summary,
                outcome="EXPIRED",
                details={"action_id": action_id}
            )
            return False, None, "The confirmation request has expired (90s limit). Please re-initiate the action."

        text = confirmation_text.lower().strip()
        
        # Unambiguous affirmative tokens
        affirmative = {"yes", "confirm", "proceed", "send it", "do it", "sure", "confirmed", "delete it", "go ahead", "yes please", "yes confirm"}
        # Explicit cancel tokens
        negative = {"no", "cancel", "stop", "abort", "don't", "dont", "never mind", "nevermind", "wait"}

        if text in affirmative or any(text == a for a in affirmative):
            del self._pending[action_id]
            audit_logger.log_event(
                event_type=f"{pending.action_type}_CONFIRMED",
                tool_name=pending.tool_name,
                target=pending.target_summary,
                outcome="USER_CONFIRMED",
                details={"action_id": action_id, "confirmation_token": text}
            )
            return True, pending, "Action confirmed by user."

        elif text in negative or any(text == n for n in negative):
            del self._pending[action_id]
            audit_logger.log_event(
                event_type=f"{pending.action_type}_CANCELLED",
                tool_name=pending.tool_name,
                target=pending.target_summary,
                outcome="USER_CANCELLED",
                details={"action_id": action_id, "reply": text}
            )
            return False, None, f"Action cancelled by user (received '{text}')."

        else:
            # Ambiguous response treated as non-confirmation
            return False, None, f"Ambiguous reply '{text}' received. Confirmation must be an explicit 'yes' or 'confirm'."


confirmation_mgr = ConfirmationManager()


# ── Path Traversal & Containment Guard ─────────────────────────────────────────

def resolve_secure_workspace_path(filename_or_path: str) -> Tuple[bool, str, str]:
    """
    Ensures a target file path resolves strictly inside DEFAULT_WORKSPACE.
    Prevents path traversal attacks (e.g. `../../sensitive.py`).
    
    Returns (is_valid: bool, resolved_path: str, error_message: str).
    """
    if not filename_or_path:
        return False, "", "No filename or path specified."

    clean = filename_or_path.strip()
    
    # If a bare filename is provided, place it inside DEFAULT_WORKSPACE
    if not os.path.isabs(clean) and not clean.startswith("~"):
        target_path = os.path.abspath(os.path.join(DEFAULT_WORKSPACE, clean))
    else:
        target_path = os.path.abspath(os.path.expanduser(clean))

    norm_workspace = os.path.normcase(os.path.abspath(DEFAULT_WORKSPACE))
    norm_target = os.path.normcase(target_path)

    # Check if target is inside workspace directory
    if not (norm_target == norm_workspace or norm_target.startswith(norm_workspace + os.sep)):
        return False, target_path, f"Path traversal blocked: target '{clean}' is outside allowed workspace directory ({DEFAULT_WORKSPACE})."

    # Also check against protected zone
    is_prot, prot_reason = protected_zone.is_path_protected(target_path)
    if is_prot:
        return False, target_path, f"Security block: {prot_reason}"

    return True, target_path, ""


# ── Grace-Period / Trash Recovery ──────────────────────────────────────────────

def move_to_trash(file_path: str) -> Tuple[bool, str]:
    """
    Moves a deleted file to the Kairos trash directory for safe recovery
    instead of immediate permanent deletion.
    """
    try:
        if not os.path.exists(file_path):
            return False, f"File '{file_path}' does not exist."
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        base_name = os.path.basename(file_path)
        trash_target = os.path.join(TRASH_DIR, f"{timestamp}_{base_name}")
        shutil.move(file_path, trash_target)
        return True, f"File safely moved to trash: {trash_target}"
    except Exception as e:
        return False, f"Failed to move file to trash: {e}"


# ── Unified Gatekeeper Validation ──────────────────────────────────────────────

def validate_tool_call(
    tool_name: str,
    params: Dict[str, Any],
    confirmed_action_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Low-level security validation gatekeeper executed before ANY tool runs in executor.py.
    
    Returns a dictionary:
      {
        "permitted": bool,
        "requires_confirmation": bool,
        "confirmation_type": str,
        "action_id": str,
        "prompt": str,
        "error_type": str,
        "message": str,
        "sanitized_params": dict
      }
    """
    # ── 1. Check Tool Allowlist ───────────────────────────────────────────────
    if tool_name not in PERMITTED_TOOLS:
        msg = f"Tool '{tool_name}' is not in the Kairos permitted tools allowlist."
        audit_logger.log_event(
            event_type="PERMISSION_DENIED",
            tool_name=tool_name,
            target="",
            outcome="BLOCKED",
            details={"reason": msg}
        )
        return {
            "permitted": False,
            "error_type": "PERMISSION_DENIED",
            "message": msg
        }

    # ── 2. Check Permanently Protected Zone (Hard Block) ──────────────────────
    is_blocked, block_reason = protected_zone.check_protected_zone(tool_name, params)
    if is_blocked:
        return {
            "permitted": False,
            "error_type": "PROTECTED_ZONE_BLOCKED",
            "message": block_reason,
            "security_alert": True
        }

    sanitized_params = dict(params)

    # ── 3. Workspace Containment for File Writing Tools ─────────────────────────
    if tool_name in ("open_notepad_and_write_code", "open_vscode_and_write_code"):
        raw_filename = params.get("filename", "code.py")
        valid, resolved_path, err = resolve_secure_workspace_path(raw_filename)
        if not valid:
            audit_logger.log_event(
                event_type="PERMISSION_DENIED",
                tool_name=tool_name,
                target=raw_filename,
                outcome="BLOCKED",
                details={"reason": err}
            )
            return {
                "permitted": False,
                "error_type": "WORKSPACE_VIOLATION",
                "message": err
            }
        sanitized_params["resolved_path"] = resolved_path

    # ── 4. Sandbox Command / Code Metacharacter Sanitization ───────────────────
    if tool_name == "write_and_run_sandbox_code":
        code = params.get("code", "")
        lang = params.get("language", "python").lower()

        # In strict mode, verify command / code sanity
        if not IS_TRUSTED_MODE and lang == "bash":
            if SHELL_METACHARACTERS_REGEX.search(code):
                msg = "Shell metacharacters (;&|`$<>) are prohibited in strict sandbox mode."
                audit_logger.log_event(
                    event_type="PERMISSION_DENIED",
                    tool_name=tool_name,
                    target="sandbox_code",
                    outcome="BLOCKED",
                    details={"reason": msg}
                )
                return {
                    "permitted": False,
                    "error_type": "SHELL_INJECTION_DETECTED",
                    "message": msg
                }

    # ── 5. Part B: Mandatory Destructive Action Detection ──────────────────────
    # Check if this tool or its parameters constitute a destructive action
    is_destructive = False
    destruct_summary = ""

    if tool_name == "delete_file":
        is_destructive = True
        target_f = params.get("filename") or params.get("path") or ""
        destruct_summary = f"Delete file: '{target_f}'"

    elif tool_name == "find_and_click":
        desc = params.get("description", "")
        if _DESTRUCTIVE_BROWSER_RE.search(desc):
            is_destructive = True
            destruct_summary = f"Irreversible web action: Click '{desc}'"

    elif tool_name == "write_and_run_sandbox_code":
        code = params.get("code", "")
        if _DESTRUCTIVE_CMD_RE.search(code):
            is_destructive = True
            destruct_summary = f"Destructive command execution in sandbox: '{code[:60]}'"

    if is_destructive:
        # If user did not supply a valid confirmation ID, hold for confirmation
        if not confirmed_action_id:
            prompt = f"Are you sure you want to permanently execute: {destruct_summary}? Please say 'yes' or 'confirm' to proceed."
            pending = confirmation_mgr.register_pending(
                action_type="DESTRUCTIVE_ACTION",
                tool_name=tool_name,
                params=sanitized_params,
                target_summary=destruct_summary,
                confirmation_prompt=prompt
            )
            return {
                "permitted": False,
                "requires_confirmation": True,
                "confirmation_type": "DESTRUCTIVE",
                "action_id": pending.action_id,
                "confirmation_prompt": prompt,
                "target_summary": destruct_summary,
                "message": f"Confirmation required before executing destructive action: {destruct_summary}"
            }

    # ── 6. Part E: Mandatory Outbound Communication Detection ──────────────────
    is_communication = False
    comm_summary = ""

    if tool_name in COMMUNICATION_TOOLS:
        recipient = params.get("recipient") or params.get("phone") or params.get("to") or ""
        message_body = params.get("message") or params.get("body") or params.get("text") or ""
        
        # Disambiguation check
        if not recipient or len(recipient.strip()) < 2:
            return {
                "permitted": False,
                "error_type": "AMBIGUOUS_RECIPIENT",
                "message": "Recipient is ambiguous or missing. Please specify the exact contact name or phone number."
            }

        is_communication = True
        comm_summary = f"Send message to '{recipient}' via {tool_name} with body: '{message_body[:80]}'"

        if not confirmed_action_id:
            prompt = f"I have prepared your message to {recipient}:\n\"{message_body}\"\nWould you like me to send this? Please confirm with 'yes' or 'send it'."
            pending = confirmation_mgr.register_pending(
                action_type="COMMUNICATION",
                tool_name=tool_name,
                params=sanitized_params,
                target_summary=comm_summary,
                confirmation_prompt=prompt
            )
            return {
                "permitted": False,
                "requires_confirmation": True,
                "confirmation_type": "COMMUNICATION",
                "action_id": pending.action_id,
                "confirmation_prompt": prompt,
                "target_summary": comm_summary,
                "message": f"Confirmation required before sending message to {recipient}."
            }

    # All checks passed
    audit_logger.log_event(
        event_type="TOOL_PERMITTED",
        tool_name=tool_name,
        target=str(sanitized_params.get("description") or sanitized_params.get("url_or_search_query") or sanitized_params.get("filename") or ""),
        outcome="PERMITTED"
    )
    return {
        "permitted": True,
        "sanitized_params": sanitized_params
    }
