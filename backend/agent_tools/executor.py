"""
executor.py — Desktop & browser automation tools for Kairos (Cross-Platform & Protected).

Key design:
1. Hardcoded Protected Zone & Security Guard: Every tool call is unconditionally inspected
   by protected_zone.py and permissions.py before execution.
2. Mandatory Two-Step Confirmation for all destructive actions (file deletion, database clear)
   and outbound communications (WhatsApp, email, etc.) with local trash recovery.
3. Browser automation runs via Playwright connected over Chrome DevTools Protocol (CDP).
4. Desktop OS automation uses PyAutoGUI in an isolated subprocess.
"""

import os
import re
import json
import shutil
import subprocess
import tempfile
import time
import threading
import urllib.parse
from typing import Optional, Dict, Any, Tuple

from agent_tools import browser
from agent_tools import native_apps
from agent_tools import permissions
from agent_tools import protected_zone
from agent_tools import audit_logger
from agent_tools import info_tools
from config import platform_paths

# ── Dynamic Python interpreter path (cross-platform) ──────────────────────────
VENV_PYTHON = platform_paths.get_venv_python_path()


def _run_auto(code: str, timeout: int = 12) -> bool:
    """
    Execute pyautogui automation code in the venv/host Python subprocess.
    Prepend standard imports/settings so callers just pass the body.
    """
    full_code = (
        "import pyautogui, time, subprocess\n"
        "pyautogui.FAILSAFE = False\n"
        "pyautogui.PAUSE = 0.05\n"
        + code
    )
    fname = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                        delete=False, encoding="utf-8") as f:
            f.write(full_code)
            fname = f.name
        
        popen_kwargs = {}
        if platform_paths.NO_WINDOW_FLAGS:
            popen_kwargs["creationflags"] = platform_paths.NO_WINDOW_FLAGS

        r = subprocess.run(
            [platform_paths.get_venv_python_path(), fname],
            capture_output=True, timeout=timeout,
            **popen_kwargs
        )
        return r.returncode == 0
    except Exception as e:
        print(f"[AUTO] Subprocess error: {e}")
        return False
    finally:
        if fname:
            try:
                os.unlink(fname)
            except Exception:
                pass


def _launch_brave(url=""):
    """Open a URL strictly in Brave — never Chrome or default browser."""
    browser.BrowserManager().launch_brave_with_cdp(url)


def _focus_brave():
    """Bring open Brave window to the foreground cross-platform."""
    app_name = "Brave" if platform_paths.IS_WINDOWS else "Brave Browser"
    platform_paths.focus_application(app_name)


# ── Confirmation Action Handler ────────────────────────────────────────────────

def confirm_pending_action(action_id: str, confirmation_text: str) -> Dict[str, Any]:
    """
    Validates user confirmation response for a pending action and executes it if confirmed.
    """
    is_confirmed, pending, reason = permissions.confirmation_mgr.validate_confirmation(action_id, confirmation_text)
    if not is_confirmed or not pending:
        return {
            "success": False,
            "message": reason,
            "action_id": action_id
        }

    # Execute the confirmed action with confirmation flag
    return execute_tool(pending.tool_name, pending.params, confirmed_action_id=action_id)


# ── Tool Dispatcher (with Unconditional Security Gatekeeper) ───────────────────

def execute_tool(tool_name: str, params: dict, confirmed_action_id: Optional[str] = None) -> dict:
    """
    Dispatches tool execution after validating against the Permission Engine and Protected Zone.
    """
    # ── Security Gatekeeper ───────────────────────────────────────────────────
    guard = permissions.validate_tool_call(tool_name, params, confirmed_action_id=confirmed_action_id)
    if not guard.get("permitted", False):
        if guard.get("requires_confirmation", False):
            return {
                "success": False,
                "requires_confirmation": True,
                "confirmation_type": guard.get("confirmation_type"),
                "action_id": guard.get("action_id"),
                "confirmation_prompt": guard.get("confirmation_prompt"),
                "message": guard.get("message"),
                "target_summary": guard.get("target_summary")
            }
        return {
            "success": False,
            "error_type": guard.get("error_type", "PERMISSION_DENIED"),
            "message": guard.get("message", "Permission denied."),
            "security_alert": guard.get("security_alert", False)
        }

    # Use sanitized parameters from permission validation
    safe_params = guard.get("sanitized_params", params)

    try:
        # ── Generic Browser Primitives (CDP / Playwright) ────────────────────
        if tool_name == "navigate_to":
            query = safe_params.get("url_or_search_query") or safe_params.get("url") or safe_params.get("query", "")
            return browser.navigate_to(query)

        elif tool_name == "find_and_click":
            desc = safe_params.get("description") or safe_params.get("element") or safe_params.get("target", "")
            return browser.find_and_click(desc)

        elif tool_name == "type_into":
            desc = safe_params.get("description") or safe_params.get("field") or safe_params.get("element", "")
            text = safe_params.get("text", "")
            press_enter = bool(safe_params.get("press_enter", False))
            return browser.type_into(desc, text, press_enter)

        elif tool_name == "scroll_page":
            return browser.scroll_page(
                direction=safe_params.get("direction", "down"),
                amount=int(safe_params.get("amount", 500))
            )

        elif tool_name in ("extract_page_text", "read_page"):
            max_chars = int(safe_params.get("max_chars", 3000))
            return browser.extract_page_text(max_chars)

        elif tool_name == "go_back":
            return browser.go_back()

        elif tool_name == "open_new_tab":
            return browser.open_new_tab(safe_params.get("url", ""))

        elif tool_name == "switch_tab":
            target = safe_params.get("index_or_description") or safe_params.get("index") or safe_params.get("description", 1)
            return browser.switch_tab(target)

        # ── Legacy YouTube Shortcuts ─────────────────────────────────────────
        elif tool_name in ("open_youtube_in_brave", "search_and_play_youtube"):
            query = safe_params.get("query", "")
            if query:
                return browser.youtube_search(query)
            return browser.navigate_to("https://www.youtube.com")

        elif tool_name == "youtube_search":
            query = safe_params.get("query", "")
            return browser.youtube_search(query)

        elif tool_name == "youtube_play_video":
            return browser.youtube_play_video(int(safe_params.get("index", 1)))

        elif tool_name == "youtube_control":
            return browser.youtube_control(safe_params.get("action", "play_pause"))

        # ── Desktop OS & Application Management ──────────────────────────────
        elif tool_name == "open_brave":
            return _open_brave()

        elif tool_name == "open_vscode":
            return _open_vscode()

        elif tool_name == "open_app":
            return _open_app(safe_params.get("app_name", "brave"))

        elif tool_name == "close_app":
            return _close_app(safe_params.get("app_name", ""))

        elif tool_name == "cursor_control":
            return _cursor_control(
                action=safe_params.get("action", "click"),
                x=safe_params.get("x"), y=safe_params.get("y"),
                text=safe_params.get("text"), key=safe_params.get("key"),
            )

        elif tool_name == "type_in_active_window":
            return _type_in_active_window(safe_params.get("text", ""))

        elif tool_name == "open_notepad_and_write_code":
            target_path = safe_params.get("resolved_path")
            return _open_notepad_write(
                filename=safe_params.get("filename", "code.py"),
                code=safe_params.get("code", ""),
                resolved_path=target_path
            )

        elif tool_name == "open_vscode_and_write_code":
            target_path = safe_params.get("resolved_path")
            return _open_vscode_write(
                filename=safe_params.get("filename", "solution.py"),
                code=safe_params.get("code", ""),
                resolved_path=target_path
            )

        elif tool_name == "write_and_run_sandbox_code":
            return {"success": True, "message": "Sandbox code ready."}

        elif tool_name == "work_mode":
            return _work_mode()

        # ── Live Real-Time Information, News & Utilities (Read-Only) ──────────
        elif tool_name == "get_current_datetime":
            tz_override = safe_params.get("timezone_override", "") or safe_params.get("timezone", "")
            return info_tools.get_current_datetime(timezone_override=tz_override)

        elif tool_name == "get_news":
            topic = safe_params.get("topic_or_location", "") or safe_params.get("topic", "") or safe_params.get("location", "") or safe_params.get("query", "")
            return info_tools.get_news(topic_or_location=topic)

        elif tool_name == "answer_general_question":
            q = safe_params.get("query", "") or safe_params.get("question", "")
            return info_tools.answer_general_question(query=q)

        # ── Destructive & Communication Tools (Executed After Confirmation) ──
        elif tool_name == "delete_file":
            target_file = safe_params.get("filename") or safe_params.get("path") or ""
            valid, resolved_p, err = permissions.resolve_secure_workspace_path(target_file)
            if not valid:
                return {"success": False, "message": err}
            ok, msg = permissions.move_to_trash(resolved_p)
            return {"success": ok, "message": msg}

        elif tool_name == "send_whatsapp_message":
            recipient = safe_params.get("recipient", "")
            body = safe_params.get("message", "")
            # Navigate to WhatsApp Web with message pre-filled
            url = f"https://web.whatsapp.com/send?text={urllib.parse.quote_plus(body)}"
            return browser.navigate_to(url)

        elif tool_name == "send_whatsapp_desktop_message":
            recipient = safe_params.get("recipient", "")
            body = safe_params.get("message", "")
            return native_apps.send_whatsapp_desktop_message(recipient, body)

        elif tool_name == "check_whatsapp_notifications":
            return browser.navigate_to("https://web.whatsapp.com")

        elif tool_name == "send_email":
            to = safe_params.get("recipient", "")
            subject = safe_params.get("subject", "")
            body = safe_params.get("body", "")
            mailto = f"mailto:{to}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
            platform_paths.launch_default_app(mailto)
            return {"success": True, "message": f"Drafted email to {to}."}

        else:
            return {"success": False, "message": f"Unknown tool: {tool_name}"}

    except Exception as e:
        audit_logger.log_event(
            event_type="TOOL_ERROR",
            tool_name=tool_name,
            target="",
            outcome="ERROR",
            details={"error": str(e)}
        )
        return {"success": False, "message": str(e)}


# ── Desktop Cursor & Keyboard ──────────────────────────────────────────────────

def _cursor_control(action, x=None, y=None, text=None, key=None):
    """OS-level mouse and keyboard automation via subprocess."""
    act = action.lower().strip()

    if act == "click":
        code = f"pyautogui.click({x}, {y})" if x is not None and y is not None else "pyautogui.click()"
    elif act == "double_click":
        code = f"pyautogui.doubleClick({x}, {y})" if x is not None and y is not None else "pyautogui.doubleClick()"
    elif act == "right_click":
        code = f"pyautogui.rightClick({x}, {y})" if x is not None and y is not None else "pyautogui.rightClick()"
    elif act == "move" and x is not None and y is not None:
        code = f"pyautogui.moveTo({x}, {y}, duration=0.3)"
    elif act == "type_text" and text:
        safe_text = text.replace("\\", "\\\\").replace('"', '\\"').replace('\n', '\\n')
        code = f'pyautogui.write("{safe_text}", interval=0.04)'
    elif act == "press_key" and key:
        code = f'pyautogui.press("{key}")'
    else:
        return {"success": False, "message": f"Unknown cursor action or missing params: {action}"}

    ok = _run_auto(code)
    return {"success": ok, "message": f"Cursor action '{action}' done."}


def _type_in_active_window(text: str) -> dict:
    """Type text into whatever OS window is currently active/focused."""
    if not text:
        return {"success": False, "message": "No text provided."}
    safe_text = text.replace("\\", "\\\\").replace('"', '\\"').replace('\n', '\\n')
    code = f"""
time.sleep(0.3)
pyautogui.write("{safe_text}", interval=0.04)
"""
    ok = _run_auto(code.strip())
    return {"success": ok, "message": "Typed text in active window."}


# ── App Management & Standalone Launchers ──────────────────────────────────────

def _open_brave() -> dict:
    """Standalone launcher: Opens or focuses Brave browser."""
    brave_exe = platform_paths.get_brave_path()
    if not brave_exe or not (os.path.exists(brave_exe) or shutil.which(brave_exe)):
        return {
            "success": False,
            "error_type": "BRAVE_NOT_FOUND",
            "message": "Brave browser is not installed or could not be found. Please install Brave or set KAIROS_BRAVE_PATH in backend/.env."
        }
    try:
        _focus_brave()
        time.sleep(0.1)
        _launch_brave()
        return {"success": True, "message": "Opened Brave Browser."}
    except Exception as e:
        return {"success": False, "message": f"Could not launch Brave Browser: {e}"}


def _open_vscode() -> dict:
    """Standalone launcher: Opens Visual Studio Code."""
    code_bin = platform_paths.get_vscode_path()
    if not code_bin or not (os.path.exists(code_bin) or shutil.which(code_bin)):
        return {
            "success": False,
            "error_type": "VSCODE_NOT_FOUND",
            "message": "Visual Studio Code is not installed or not found on PATH. Please install VS Code or set KAIROS_VSCODE_PATH in backend/.env."
        }
    try:
        popen_kwargs = {}
        if platform_paths.NO_WINDOW_FLAGS:
            popen_kwargs["creationflags"] = platform_paths.NO_WINDOW_FLAGS
        subprocess.Popen([code_bin], **popen_kwargs)
        return {"success": True, "message": "Opened VS Code."}
    except Exception as e:
        return {"success": False, "message": f"Could not open VS Code: {e}"}


def _open_app(app_name: str) -> dict:
    key = app_name.lower().strip()
    if key in ("brave", "brave browser"):
        return _open_brave()

    if key in ("code", "vscode", "vs code", "visual studio code"):
        return _open_vscode()

    if key in ("chrome", "google chrome"):
        chrome_exe = platform_paths.get_chrome_path()
        if not chrome_exe or not (os.path.exists(chrome_exe) or shutil.which(chrome_exe)):
            return {
                "success": False,
                "error_type": "CHROME_NOT_FOUND",
                "message": "Google Chrome is not installed or could not be found. Please install Chrome or set KAIROS_CHROME_PATH in backend/.env."
            }
        try:
            popen_kwargs = {}
            if platform_paths.NO_WINDOW_FLAGS:
                popen_kwargs["creationflags"] = platform_paths.NO_WINDOW_FLAGS
            subprocess.Popen([chrome_exe], **popen_kwargs)
            return {"success": True, "message": "Opened Google Chrome."}
        except Exception as e:
            return {"success": False, "message": f"Could not launch Google Chrome: {e}"}

    if key in ("whatsapp", "whatsapp desktop"):
        try:
            ok = platform_paths.launch_default_app("whatsapp:")
            if ok:
                return {"success": True, "message": "Opened WhatsApp Desktop."}
        except Exception as _wa_err:
            print(f"[PlatformPaths] WhatsApp URI launch warning: {_wa_err}")

    if key in ("notepad", "editor", "text editor"):
        try:
            temp_file = os.path.join(permissions.DEFAULT_WORKSPACE, "notes.txt")
            if not os.path.exists(temp_file):
                with open(temp_file, "w", encoding="utf-8") as f:
                    f.write("")
            cmd = platform_paths.get_text_editor_command(temp_file)
            popen_kwargs = {}
            if platform_paths.NO_WINDOW_FLAGS:
                popen_kwargs["creationflags"] = platform_paths.NO_WINDOW_FLAGS
            subprocess.Popen(cmd, **popen_kwargs)
            return {"success": True, "message": f"Opened text editor ({cmd[0]})."}
        except Exception as e:
            return {"success": False, "message": f"Could not open text editor: {e}"}

    ok = platform_paths.launch_default_app(key)
    if ok:
        return {"success": True, "message": f"Opened {app_name}."}

    which_bin = shutil.which(key)
    if which_bin:
        try:
            popen_kwargs = {}
            if platform_paths.NO_WINDOW_FLAGS:
                popen_kwargs["creationflags"] = platform_paths.NO_WINDOW_FLAGS
            subprocess.Popen([which_bin], **popen_kwargs)
            return {"success": True, "message": f"Launched {app_name}."}
        except Exception as e:
            return {"success": False, "message": f"Could not launch {app_name}: {e}"}

    return {"success": False, "message": f"Could not find or open {app_name} on {platform_paths.SYSTEM}."}


def _close_app(app_name: str) -> dict:
    key = app_name.lower().strip()
    alias_map = {
        "calculator": "calc",
        "vs code": "code",
        "vscode": "code",
        "visual studio code": "code",
        "terminal": "WindowsTerminal" if platform_paths.IS_WINDOWS else "terminal",
        "browser": "brave",
    }
    proc_name = alias_map.get(key, key)
    ok = platform_paths.kill_process_by_name(proc_name)
    if ok:
        return {"success": True, "message": f"Closed {app_name}."}
    return {"success": False, "message": f"Could not close {app_name}."}


# ── Work Mode (Google Chrome CDP + VS Code Workspace) ──────────────────────────

def _work_mode() -> dict:
    """
    Activates Work Mode:
    Verifies Google Chrome presence and opens developer sites (GitHub, LeetCode, Gmail, ChatGPT)
    in Chrome via CDP, and launches VS Code in the configured default workspace.
    """
    chrome_exe = platform_paths.get_chrome_path()
    if not chrome_exe or not (os.path.exists(chrome_exe) or shutil.which(chrome_exe)):
        return {
            "success": False,
            "error_type": "CHROME_NOT_FOUND",
            "message": "Google Chrome is not installed or could not be found. Work Mode specifically requires Google Chrome. Please install Chrome or set KAIROS_CHROME_PATH in backend/.env."
        }

    return browser.run_work_mode()


def _open_notepad_write(filename="code.py", code="", resolved_path=None):
    """Write code into workspace file and open in platform text editor."""
    if not code or not code.strip():
        return {
            "success": False,
            "error_type": "EMPTY_CODE",
            "message": "No code content was provided to write to Notepad."
        }
    try:
        clean_name = os.path.basename(filename) if filename else "code.py"
        filepath = resolved_path or os.path.join(permissions.DEFAULT_WORKSPACE, clean_name)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)

        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            return {
                "success": False,
                "error_type": "DISK_WRITE_FAILED",
                "message": f"Failed to write code to disk at '{filepath}'."
            }

        cmd = platform_paths.get_text_editor_command(filepath)
        popen_kwargs = {}
        if platform_paths.NO_WINDOW_FLAGS:
            popen_kwargs["creationflags"] = platform_paths.NO_WINDOW_FLAGS
        proc = subprocess.Popen(cmd, **popen_kwargs)
        if isinstance(proc.poll(), int) and proc.poll() != 0:
            return {
                "success": False,
                "error_type": "EDITOR_LAUNCH_FAILED",
                "message": f"Text editor process exited prematurely with code {proc.poll()}."
            }

        return {
            "success": True,
            "message": f"Created {clean_name} with your Python code and opened it in Notepad.",
            "filepath": filepath,
            "filename": clean_name,
            "editor": cmd[0]
        }
    except Exception as e:
        return {"success": False, "error_type": "EDITOR_ERROR", "message": f"Editor error: {e}"}


def _open_vscode_write(filename="solution.py", code="", resolved_path=None):
    """Write code into workspace file and open in VS Code."""
    if not code or not code.strip():
        return {
            "success": False,
            "error_type": "EMPTY_CODE",
            "message": "No code content was provided to write to VS Code."
        }
    try:
        clean_name = os.path.basename(filename) if filename else "solution.py"
        filepath = resolved_path or os.path.join(permissions.DEFAULT_WORKSPACE, clean_name)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)

        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            return {
                "success": False,
                "error_type": "DISK_WRITE_FAILED",
                "message": f"Failed to write code to disk at '{filepath}'."
            }

        code_bin = platform_paths.get_vscode_path()
        if not code_bin or not (os.path.exists(code_bin) or shutil.which(code_bin)):
            return {
                "success": False,
                "error_type": "VSCODE_NOT_FOUND",
                "message": "Visual Studio Code is not installed or not found on PATH. Please install VS Code or set KAIROS_VSCODE_PATH in backend/.env."
            }

        popen_kwargs = {}
        if platform_paths.NO_WINDOW_FLAGS:
            popen_kwargs["creationflags"] = platform_paths.NO_WINDOW_FLAGS
        proc = subprocess.Popen([code_bin, filepath], **popen_kwargs)
        return {
            "success": True,
            "message": f"Created {clean_name} and opened it in VS Code.",
            "filepath": filepath,
            "filename": clean_name
        }
    except Exception as e:
        return {"success": False, "error_type": "VSCODE_ERROR", "message": f"VS Code error: {e}"}


# ── Action tag parsing ─────────────────────────────────────────────────────────
_ACTION_RE = re.compile(r'\[ACTION:(\{.*?\})\]', re.DOTALL)


def _try_fix_json(raw):
    for extra in ["", "}", "}}", "\"}", "\"}}"]:
        try:
            return json.loads(raw + extra)
        except json.JSONDecodeError:
            continue
    return None


def extract_action(text):
    m = _ACTION_RE.search(text)
    if not m:
        loose = re.search(r'\[ACTION:(\{[^\]]*)', text, re.DOTALL)
        if not loose:
            return None
        return _try_fix_json(loose.group(1))
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return _try_fix_json(m.group(1))


def strip_action_tag(text):
    cleaned = _ACTION_RE.sub("", text)
    cleaned = re.sub(r'\[ACTION:\{[^\]]*', "", cleaned)
    return cleaned.strip()
