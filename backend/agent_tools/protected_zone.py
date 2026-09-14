"""
protected_zone.py — Permanently Protected Zone for Kairos.

Defines hardcoded, non-configurable security boundaries that Kairos can NEVER read,
write, modify, delete, execute against, or interact with via any tool, command, or browser action.
This protection applies unconditionally across ALL modes (including trusted mode) and
cannot be overridden by runtime configuration, plugins, LLM instructions, or user voice commands.
"""

import os
import re
from typing import Tuple, Optional, List, Dict, Any

from agent_tools import audit_logger

# ── Base System Directories ───────────────────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
USER_HOME = os.path.expanduser("~")

# ── Hardcoded Protected Files & Security Core ─────────────────────────────────
CORE_SECURITY_FILES = {
    os.path.abspath(os.path.join(BACKEND_DIR, "agent_tools", "protected_zone.py")),
    os.path.abspath(os.path.join(BACKEND_DIR, "agent_tools", "permissions.py")),
    os.path.abspath(os.path.join(BACKEND_DIR, "agent_tools", "audit_logger.py")),
    os.path.abspath(os.path.join(BACKEND_DIR, "agent_tools", "SECURITY.md")),
    os.path.abspath(audit_logger.AUDIT_LOG_FILE),
    os.path.abspath(os.path.join(BACKEND_DIR, ".env")),
}

# ── Protected Directory Prefixes ──────────────────────────────────────────────
SYSTEM_PROTECTED_DIR_PREFIXES = [
    # Windows system roots
    r"C:\Windows",
    r"C:\Program Files\Windows",
    r"C:\ProgramData\Microsoft",
    # Unix system roots
    "/etc",
    "/usr/bin",
    "/usr/sbin",
    "/bin",
    "/sbin",
    "/System",
    "/Library/System",
    "/root",
    "/var/root",
    "/dev",
    "/proc",
    "/sys",
    # Credential & Key directories in user home
    os.path.join(USER_HOME, ".ssh"),
    os.path.join(USER_HOME, ".aws"),
    os.path.join(USER_HOME, ".gnupg"),
    os.path.join(USER_HOME, ".config", "gcloud"),
    os.path.join(USER_HOME, ".azure"),
]

# Sensitive file patterns (credentials, keys, tokens, session databases)
SENSITIVE_FILE_REGEX = re.compile(
    r"(\.env(\..+)?$|id_rsa|id_ed25519|id_ecdsa|\.pem$|\.key$|\.pfx$|\.p12$|\.crt$|"
    r"Login Data|Cookies|Web Data|key4\.db|logins\.json)",
    re.IGNORECASE
)

# ── Financial & Payment Action Hard-Block Patterns ────────────────────────────
# Financial actions cannot be executed or submitted by Kairos under any circumstances.
FINANCIAL_PAYMENT_PATTERNS = [
    # Payment execution & submission
    r"\bpay\s+now\b",
    r"\bbuy\s+now\b",
    r"\bconfirm\s+(payment|purchase|order)\b",
    r"\bplace\s+order\b",
    r"\bcomplete\s+(payment|purchase|checkout)\b",
    r"\bsubmit\s+(payment|order)\b",
    r"\bauthori[sz]e\s+payment\b",
    r"\bmake\s+payment\b",
    r"\btransfer\s+money\b",
    r"\bwire\s+transfer\b",
    r"\bsend\s+money\b",
    r"\bcheckout\s+payment\b",
    # Sensitive Financial Input Fields
    r"\bcredit\s*card\b",
    r"\bdebit\s*card\b",
    r"\bcard\s*number\b",
    r"\bcvv\b",
    r"\bcvc\b",
    r"\bsecurity\s*code\b",
    r"\bcard\s*expir(y|ation)\b",
    r"\bbank\s*account\b",
    r"\brouting\s*number\b",
]

_FINANCIAL_RE = re.compile("|".join(FINANCIAL_PAYMENT_PATTERNS), re.IGNORECASE)


def load_user_protected_paths() -> List[str]:
    """Loads additional custom protected paths defined in backend/config/protected_paths.txt."""
    custom_paths = []
    config_file = os.path.join(BACKEND_DIR, "config", "protected_paths.txt")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        expanded = os.path.abspath(os.path.expanduser(line))
                        custom_paths.append(expanded)
        except Exception as e:
            print(f"[ProtectedZone] Failed to load protected_paths.txt: {e}")
    return custom_paths


def is_path_protected(path_str: str, allow_read_for_user_paths: bool = False) -> Tuple[bool, str]:
    """
    Checks if a filesystem path falls into the Permanently Protected Zone.
    Returns (is_protected: bool, reason: str).
    """
    if not path_str:
        return False, ""

    try:
        norm_path = os.path.abspath(os.path.expanduser(path_str.strip()))
    except Exception:
        norm_path = path_str.strip()

    # 1. Check Core Security & Audit Files
    if norm_path in CORE_SECURITY_FILES:
        return True, f"Target path '{norm_path}' is an internal Kairos security/audit file."

    for sec_file in CORE_SECURITY_FILES:
        if os.path.normcase(norm_path) == os.path.normcase(sec_file):
            return True, f"Target path '{norm_path}' matches protected security file."

    # 2. Check System Protected Directory Prefixes
    norm_case_path = os.path.normcase(norm_path)
    for prefix in SYSTEM_PROTECTED_DIR_PREFIXES:
        norm_prefix = os.path.normcase(os.path.abspath(prefix))
        if norm_case_path == norm_prefix or norm_case_path.startswith(norm_prefix + os.sep):
            return True, f"Target path '{norm_path}' is inside protected system directory '{prefix}'."

    # 3. Check Sensitive File Patterns (Credentials, Keys, Tokens)
    filename = os.path.basename(norm_path)
    if SENSITIVE_FILE_REGEX.search(filename):
        return True, f"Target file '{filename}' contains credentials/secrets matching protected pattern."

    # 4. Check User Custom Protected Paths
    user_paths = load_user_protected_paths()
    for upath in user_paths:
        norm_upath = os.path.normcase(upath)
        if norm_case_path == norm_upath or norm_case_path.startswith(norm_upath + os.sep):
            if not allow_read_for_user_paths:
                return True, f"Target path '{norm_path}' is in user-configured protected path '{upath}'."

    return False, ""


def is_financial_action(description_or_text: str) -> Tuple[bool, str]:
    """
    Checks if an action description, button label, or typed text involves payments or purchases.
    Returns (is_financial: bool, reason: str).
    """
    if not description_or_text:
        return False, ""
    
    m = _FINANCIAL_RE.search(description_or_text)
    if m:
        matched = m.group(0)
        return True, f"Financial/payment action or credential entry blocked: matched '{matched}'."
    
    return False, ""


def check_protected_zone(
    tool_name: str,
    params: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Comprehensive gatekeeper evaluating whether a tool invocation attempts to touch
    the Protected Zone.
    
    Returns (is_blocked: bool, block_reason: str).
    If blocked, immediately logs a SECURITY_ALERT audit event.
    """
    # 1. Inspect any file path parameter
    path_keys = ["filename", "filepath", "path", "target", "file", "dest", "destination"]
    for pk in path_keys:
        val = params.get(pk)
        if isinstance(val, str) and val.strip():
            blocked, reason = is_path_protected(val)
            if blocked:
                audit_logger.log_event(
                    event_type="PROTECTED_ZONE_BLOCKED",
                    tool_name=tool_name,
                    target=val,
                    outcome="BLOCKED",
                    details={"param_key": pk, "reason": reason},
                    severity="SECURITY_ALERT"
                )
                return True, f"SECURITY BLOCK: Access to protected resource denied. {reason}"

    # 2. Inspect text content / code / input for secret file writes or credentials
    text_keys = ["code", "text", "content"]
    for tk in text_keys:
        val = params.get(tk)
        if isinstance(val, str) and val.strip():
            # Check financial details in text inputs
            fin_blocked, fin_reason = is_financial_action(val)
            if fin_blocked:
                audit_logger.log_event(
                    event_type="PROTECTED_ZONE_BLOCKED",
                    tool_name=tool_name,
                    target=val[:60],
                    outcome="BLOCKED",
                    details={"param_key": tk, "reason": fin_reason},
                    severity="SECURITY_ALERT"
                )
                return True, f"SECURITY BLOCK: Financial/payment data entry is strictly prohibited. {fin_reason}"

    # 3. Inspect Browser Automation actions (find_and_click, type_into, navigate_to)
    if tool_name in ("find_and_click", "type_into", "navigate_to"):
        desc = params.get("description") or params.get("url_or_search_query") or params.get("element") or ""
        if isinstance(desc, str):
            fin_blocked, fin_reason = is_financial_action(desc)
            if fin_blocked:
                audit_logger.log_event(
                    event_type="PROTECTED_ZONE_BLOCKED",
                    tool_name=tool_name,
                    target=desc,
                    outcome="BLOCKED",
                    details={"tool": tool_name, "description": desc, "reason": fin_reason},
                    severity="SECURITY_ALERT"
                )
                return True, f"SECURITY BLOCK: Financial/payment actions are permanently off-limits. {fin_reason}"

    return False, ""
