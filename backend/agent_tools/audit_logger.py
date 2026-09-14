"""
audit_logger.py — Structured Audit Logging for Kairos Actions & Security Events.

Records all tool executions, permission denials, protected-zone blocks,
and confirmation lifecycles (requested, confirmed, cancelled) to backend/logs/tool_audit.log.
"""

import os
import json
import time
import datetime
import threading
from typing import Dict, Any, Optional

# ── Log file path ─────────────────────────────────────────────────────────────
def _get_data_dir() -> str:
    """Return writable Kairos user data directory."""
    override = os.environ.get("KAIROS_DATA_DIR")
    if override:
        return override.strip().strip('"\'')
    if os.name == "nt":
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~/AppData/Roaming")
        return os.path.join(appdata, "Kairos")
    return os.path.expanduser("~/.kairos")

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(_get_data_dir(), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
AUDIT_LOG_FILE = os.path.join(LOGS_DIR, "tool_audit.log")

_lock = threading.Lock()

def _ensure_log_dir():
    try:
        if not os.path.exists(LOGS_DIR):
            os.makedirs(LOGS_DIR, exist_ok=True)
    except Exception as e:
        print(f"[AuditLogger] Failed to create logs directory: {e}")


def log_event(
    event_type: str,
    tool_name: str,
    target: str,
    outcome: str,
    details: Optional[Dict[str, Any]] = None,
    severity: str = "INFO"
):
    """
    Appends a structured JSON line entry to tool_audit.log.
    
    event_type:
      - TOOL_EXECUTION
      - PERMISSION_DENIED
      - PROTECTED_ZONE_BLOCKED
      - DESTRUCTIVE_ACTION_PENDING
      - DESTRUCTIVE_ACTION_CONFIRMED
      - DESTRUCTIVE_ACTION_CANCELLED
      - COMMUNICATION_PENDING
      - COMMUNICATION_CONFIRMED
      - COMMUNICATION_CANCELLED
    """
    _ensure_log_dir()
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "epoch": time.time(),
        "severity": severity.upper(),
        "event_type": event_type,
        "tool_name": tool_name,
        "target": target,
        "outcome": outcome,
        "details": details or {}
    }

    try:
        line = json.dumps(entry, ensure_ascii=False)
        with _lock:
            with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception as e:
        print(f"[AuditLogger] Failed to write to audit log: {e}")
