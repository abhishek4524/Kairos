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
from agent_tools import file_tools
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

        # ── YouTube Automation (Google Chrome Default Profile) ───────────────
        elif tool_name in ("open_youtube_in_brave", "search_and_play_youtube"):
            query = safe_params.get("query") or safe_params.get("search_query") or safe_params.get("q", "")
            if query:
                s_res = browser.youtube_search(query)
                if s_res.get("success"):
                    time.sleep(0.5)
                    return browser.youtube_play_video(1)
                return s_res
            return browser.navigate_to("https://www.youtube.com")

        elif tool_name == "youtube_search":
            query = safe_params.get("query") or safe_params.get("search_query") or safe_params.get("q", "")
            s_res = browser.youtube_search(query)
            if query and s_res.get("success"):
                time.sleep(0.5)
                return browser.youtube_play_video(1)
            return s_res

        elif tool_name == "youtube_play_video":
            return browser.youtube_play_video(int(safe_params.get("index", 1)))

        elif tool_name == "youtube_control":
            return browser.youtube_control(safe_params.get("action", "play_pause"))

        elif tool_name == "youtube_like_video":
            return browser.youtube_like_video()

        elif tool_name == "youtube_subscribe":
            return browser.youtube_subscribe()

        elif tool_name == "open_github":
            return browser.open_github(safe_params.get("path", ""))

        elif tool_name == "open_instagram":
            return browser.open_instagram(safe_params.get("path", ""))

        elif tool_name == "instagram_action":
            return browser.instagram_action(safe_params.get("action", ""), safe_params.get("target", ""))

        # ── Camera Gesture Control ──────────────────────────────────────────
        elif tool_name == "start_camera_gesture_control":
            from agent_tools.gesture_control import get_gesture_controller
            gc = get_gesture_controller()
            show_preview = bool(safe_params.get("show_preview", False))
            return gc.start(show_preview=show_preview)

        elif tool_name == "stop_camera_gesture_control":
            from agent_tools.gesture_control import get_gesture_controller
            gc = get_gesture_controller()
            return gc.stop()

        elif tool_name == "get_camera_gesture_status":
            from agent_tools.gesture_control import get_gesture_controller
            gc = get_gesture_controller()
            return {"success": True, "status": gc.get_status()}

        elif tool_name == "set_camera_gesture_mode":
            from agent_tools.gesture_control import get_gesture_controller
            gc = get_gesture_controller()
            mode = str(safe_params.get("mode", "system"))
            return gc.set_mode(mode)

        elif tool_name == "get_facial_expression":
            from agent_tools.gesture_control import get_gesture_controller
            gc = get_gesture_controller()
            return {"success": True, "expression": gc.get_facial_expression()}

        # ── Desktop OS & Application Management ──────────────────────────────
        elif tool_name == "open_brave":
            return _open_brave()

        elif tool_name == "open_vscode":
            return _open_vscode()

        elif tool_name in ("open_app", "app_control"):
            target_app = safe_params.get("app_name") or safe_params.get("app") or safe_params.get("name") or "brave"
            return _open_app(target_app)

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

        elif tool_name in ("open_notepad_and_write_code", "write_to_notepad", "notepad_write"):
            target_path = safe_params.get("resolved_path")
            # Accept either "code" or "text" or "content" param
            content = (
                safe_params.get("text")
                or safe_params.get("code")
                or safe_params.get("content")
                or ""
            )
            filename = safe_params.get("filename", "note.txt")
            return _open_notepad_write(
                filename=filename,
                code=content,
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

        # ── File & Folder Management Tools ────────────────────────────────────
        elif tool_name == "create_folder":
            name = safe_params.get("folder_name") or safe_params.get("name") or safe_params.get("path") or safe_params.get("target_path") or ""
            parent = safe_params.get("parent_dir") or safe_params.get("location") or safe_params.get("dir")
            return file_tools.create_folder(folder_name=name, parent_dir=parent)

        elif tool_name == "create_file":
            fname = safe_params.get("filename") or safe_params.get("name") or safe_params.get("path") or safe_params.get("file") or ""
            text_content = safe_params.get("content") or safe_params.get("text") or safe_params.get("code") or ""
            parent = safe_params.get("parent_dir") or safe_params.get("location") or safe_params.get("dir")
            return file_tools.create_file(filename=fname, content=text_content, parent_dir=parent)

        elif tool_name == "rename_file_or_folder":
            old_n = safe_params.get("old_name") or safe_params.get("old_path") or safe_params.get("original_name") or safe_params.get("from") or ""
            new_n = safe_params.get("new_name") or safe_params.get("new_path") or safe_params.get("target_name") or safe_params.get("to") or ""
            parent = safe_params.get("parent_dir") or safe_params.get("location") or safe_params.get("dir")
            return file_tools.rename_file_or_folder(old_name=old_n, new_name=new_n, parent_dir=parent)

        elif tool_name == "list_directory_contents":
            dir_p = safe_params.get("path") or safe_params.get("dir") or safe_params.get("folder") or "desktop"
            return file_tools.list_directory_contents(path=dir_p)

        elif tool_name in ("open_cmd", "run_cmd", "run_command", "exec_cmd", "execute_command", "propose_terminal_command", "run_terminal_command"):
            cmd_arg = safe_params.get("command") or safe_params.get("cmd") or safe_params.get("natural_request") or safe_params.get("input") or ""
            return _execute_cmd_command(cmd_arg)

        # ── Live Real-Time Information, News & Utilities (Read-Only) ──────────
        elif tool_name == "get_current_datetime":
            tz_override = safe_params.get("timezone_override", "") or safe_params.get("timezone", "")
            return info_tools.get_current_datetime(timezone_override=tz_override)

        elif tool_name == "get_weather":
            city = safe_params.get("city", "") or safe_params.get("location", "") or safe_params.get("query", "")
            country = safe_params.get("country", "")
            return info_tools.get_weather(city=city, country=country)

        elif tool_name == "get_news":
            topic = safe_params.get("topic_or_location", "") or safe_params.get("topic", "") or safe_params.get("location", "") or safe_params.get("query", "")
            return info_tools.get_news(topic_or_location=topic)

        elif tool_name in ("answer_general_question", "web_search", "search_web", "google_search"):
            q = safe_params.get("query", "") or safe_params.get("question", "") or safe_params.get("q", "") or safe_params.get("search_query", "")
            return info_tools.answer_general_question(query=q)

        elif tool_name == "query_spreadsheet":
            doc_name = safe_params.get("doc_name", "") or safe_params.get("filename", "")
            q = safe_params.get("query", "") or safe_params.get("question", "")
            return info_tools.query_spreadsheet(doc_name=doc_name, query=q)

        # ── Destructive & Communication Tools (Executed After Confirmation) ──
        elif tool_name == "delete_file":
            target_file = safe_params.get("target_file_path") or safe_params.get("filename") or safe_params.get("path") or ""
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

        elif tool_name == "open_whatsapp_chat":
            recipient = safe_params.get("recipient") or safe_params.get("contact_name") or safe_params.get("contact") or safe_params.get("name") or ""
            return native_apps.open_whatsapp_chat(recipient)

        elif tool_name == "send_whatsapp_desktop_message":
            recipient = safe_params.get("recipient") or safe_params.get("contact_name") or safe_params.get("contact") or safe_params.get("name") or ""
            body = safe_params.get("message") or safe_params.get("text") or safe_params.get("body") or ""
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

        # ── Developer Superpowers Tools ────────────────────────────────────────
        elif tool_name == "get_project_context":
            from agent_tools import dev_tools
            return dev_tools.get_project_context(repo_root=safe_params.get("repo_root"))

        elif tool_name == "query_codebase":
            from agent_tools import dev_tools
            q = safe_params.get("query", "")
            results = dev_tools.query_codebase(query=q, top_k=safe_params.get("top_k", 4))
            return {"success": True, "results": results, "count": len(results)}

        elif tool_name == "propose_terminal_command":
            from agent_tools import dev_tools
            return dev_tools.propose_terminal_command(natural_request=safe_params.get("natural_request", ""))

        elif tool_name == "run_terminal_command":
            from agent_tools import dev_tools
            return dev_tools.execute_terminal_command(
                command=safe_params.get("command", ""),
                cwd=safe_params.get("cwd")
            )

        elif tool_name == "explain_git_diff":
            from agent_tools import dev_tools
            return dev_tools.explain_git_diff(
                staged_only=safe_params.get("staged_only", False),
                repo_root=safe_params.get("repo_root")
            )

        elif tool_name == "explain_error":
            from agent_tools import dev_tools
            return dev_tools.explain_error(
                stack_trace=safe_params.get("stack_trace", ""),
                repo_root=safe_params.get("repo_root")
            )

        elif tool_name == "activate_hackathon_mode":
            from agent_tools import dev_tools
            return dev_tools.activate_hackathon_mode(
                deadline_hours=safe_params.get("deadline_hours", 24.0),
                repo_root=safe_params.get("repo_root")
            )

        elif tool_name == "activate_focus_mode":
            from agent_tools import dev_tools
            return dev_tools.activate_focus_mode(
                duration_minutes=safe_params.get("duration_minutes", 25),
                blocked_sites=safe_params.get("blocked_sites")
            )

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

def _adjust_system_brightness(delta: int = 0, level: Optional[int] = None) -> dict:
    """Adjust system screen brightness on Windows via WMI."""
    if not platform_paths.IS_WINDOWS:
        return {"success": False, "message": "Brightness adjustment is currently supported on Windows."}
    try:
        if level is not None:
            target = max(0, min(100, level))
        else:
            try:
                cmd_get = 'powershell -Command "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness).CurrentBrightness"'
                out = subprocess.check_output(cmd_get, shell=True, text=True).strip()
                curr = int(out) if out.isdigit() else 70
            except Exception:
                curr = 70
            target = max(0, min(100, curr + delta))

        cmd_set = f'powershell -Command "(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {target})"'
        subprocess.run(cmd_set, shell=True, check=True)
        return {"success": True, "message": f"Set screen brightness to {target}%."}
    except Exception as e:
        try:
            presses = 10 if delta < 0 else 10
            key_name = 'brightnessdown' if delta < 0 else 'brightnessup'
            code = f'pyautogui.press("{key_name}", presses={presses})'
            _run_auto(code)
            return {"success": True, "message": "Adjusted screen brightness."}
        except Exception:
            return {"success": False, "message": f"Could not adjust brightness: {e}"}


def _adjust_system_volume(delta: int = 0, mute: bool = False) -> dict:
    """Adjust master system audio volume on Windows."""
    try:
        if mute:
            code = 'pyautogui.press("volumemute")'
            _run_auto(code)
            return {"success": True, "message": "Toggled volume mute."}

        if delta > 0:
            presses = 25 if delta >= 40 else 10
            code = f'pyautogui.press("volumeup", presses={presses})'
            _run_auto(code)
            return {"success": True, "message": "Increased volume."}
        else:
            presses = 25 if delta <= -40 else 10
            code = f'pyautogui.press("volumedown", presses={presses})'
            _run_auto(code)
            return {"success": True, "message": "Decreased volume."}
    except Exception as e:
        return {"success": False, "message": f"Could not adjust volume: {e}"}


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
        k = key.lower().strip()
        if k in ("volume_down", "volumedown", "volume down"):
            return _adjust_system_volume(delta=-15)
        elif k in ("volume_up", "volumeup", "volume up", "volume_max", "volumemax", "volume max"):
            return _adjust_system_volume(delta=50 if "max" in k else 15)
        elif k in ("volume_mute", "volumemute", "mute"):
            return _adjust_system_volume(mute=True)
        elif k in ("brightness_down", "brightnessdown", "brightness down"):
            return _adjust_system_brightness(delta=-25)
        elif k in ("brightness_up", "brightnessup", "brightness up", "brightness_max", "brightnessmax", "brightness max"):
            return _adjust_system_brightness(delta=50 if "max" in k else 25)
        else:
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
try:
    import pyperclip
    pyperclip.copy("{safe_text}")
    pyautogui.hotkey('ctrl', 'v')
except Exception:
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

    if key in ("file explorer", "explorer", "files", "folder", "my computer", "this pc"):
        try:
            if platform_paths.IS_WINDOWS:
                subprocess.Popen(["explorer.exe"])
                return {"success": True, "message": "Opened File Explorer."}
            else:
                ok = platform_paths.launch_default_app(".")
                if ok:
                    return {"success": True, "message": "Opened File Manager."}
        except Exception as e:
            return {"success": False, "message": f"Could not open File Explorer: {e}"}

    if key in ("browser", "web browser"):
        chrome_exe = platform_paths.get_chrome_path()
        if chrome_exe and (os.path.exists(chrome_exe) or shutil.which(chrome_exe)):
            return _open_app("chrome")
        return _open_brave()

    if key in ("calc", "calculator"):
        try:
            popen_kwargs = {}
            if platform_paths.NO_WINDOW_FLAGS:
                popen_kwargs["creationflags"] = platform_paths.NO_WINDOW_FLAGS
            subprocess.Popen(["calc.exe" if platform_paths.IS_WINDOWS else "calculator"], **popen_kwargs)
            return {"success": True, "message": "Opened Calculator."}
        except Exception as e:
            return {"success": False, "message": f"Could not open Calculator: {e}"}

    if key in ("camera", "webcam", "windows camera", "camera app"):
        try:
            if platform_paths.IS_WINDOWS:
                os.startfile("microsoft.windows.camera:")
                return {"success": True, "message": "Opened Windows Camera."}
            else:
                ok = platform_paths.launch_default_app("camera")
                if ok:
                    return {"success": True, "message": "Opened Camera."}
                return {"success": False, "message": "Could not open Camera on this platform."}
        except Exception as e:
            return {"success": False, "message": f"Could not open Camera: {e}"}

    if key in ("terminal", "command prompt", "cmd", "powershell"):
        try:
            cmd = ["powershell.exe"] if platform_paths.IS_WINDOWS else ["terminal"]
            subprocess.Popen(cmd)
            return {"success": True, "message": "Opened Terminal."}
        except Exception as e:
            return {"success": False, "message": f"Could not open Terminal: {e}"}

    if key in ("youtube", "youtube.com", "youtube desktop"):
        return browser.navigate_to("https://www.youtube.com")

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


def _execute_cmd_command(cmd_str: str) -> dict:
    """
    Executes a shell/CMD command or intelligently maps mkdir, touch, ren, echo to file_tools.
    """
    if not cmd_str or not str(cmd_str).strip():
        return {"success": False, "message": "No command provided."}

    raw = str(cmd_str).strip()
    expanded_cmd = os.path.expandvars(raw)

    # 1. Parse mkdir / md commands
    mkdir_match = re.match(r"^(?:mkdir|md)\s+(.+)$", expanded_cmd, re.I)
    if mkdir_match:
        target_path = mkdir_match.group(1).strip().strip("\"'")
        return file_tools.create_folder(folder_name=target_path)

    # 2. Parse touch or echo > commands for file creation
    touch_match = re.match(r"^(?:touch|type\s+nul\s*>\s*)\s*(.+)$", expanded_cmd, re.I)
    if touch_match:
        target_path = touch_match.group(1).strip().strip("\"'")
        return file_tools.create_file(filename=target_path)

    echo_match = re.match(r"^echo\s+(.*?)\s*>\s*(.+)$", expanded_cmd, re.I)
    if echo_match:
        content = echo_match.group(1).strip().strip("\"'")
        target_path = echo_match.group(2).strip().strip("\"'")
        return file_tools.create_file(filename=target_path, content=content)

    # 3. Parse ren / move commands
    ren_match = re.match(r"^(?:ren|rename|move)\s+(?:\"([^\"]+)\"|(\S+))\s+(?:\"([^\"]+)\"|(\S+))$", expanded_cmd, re.I)
    if ren_match:
        old_p = ren_match.group(1) or ren_match.group(2)
        new_p = ren_match.group(3) or ren_match.group(4)
        return file_tools.rename_file_or_folder(old_name=old_p, new_name=new_p)

    # 4. Fallback execution via CMD / Shell Subprocess
    try:
        if platform_paths.IS_WINDOWS:
            proc = subprocess.run(["cmd.exe", "/c", expanded_cmd], capture_output=True, text=True, timeout=10)
        else:
            proc = subprocess.run(expanded_cmd, shell=True, capture_output=True, text=True, timeout=10)
        out = (proc.stdout or proc.stderr or "").strip()
        return {
            "success": proc.returncode == 0,
            "message": out or f"Executed command: {raw}",
            "returncode": proc.returncode
        }
    except Exception as e:
        return {"success": False, "message": f"Command execution failed: {e}"}


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
    """Write content to a file and open it in the system text editor (Notepad on Windows)."""
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
                "message": f"Failed to write content to disk at '{filepath}'."
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
            "editor": cmd[0],
            "content_preview": code[:100] + ("..." if len(code) > 100 else "")
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


class ActionTagStreamFilter:
    """
    Stream state machine that filters out [ACTION:{...}] tags across chunk boundaries
    so raw JSON fragments never leak to TTS or chat bubbles.
    """
    def __init__(self):
        self._in_action_tag = False
        self._in_string = False
        self._escape_next = False
        self._brace_depth = 0
        self._bracket_depth = 0
        self._pending_prefix = ""

    def filter_chunk(self, chunk: str) -> str:
        text = self._pending_prefix + chunk
        self._pending_prefix = ""
        output = []
        i = 0
        n = len(text)

        while i < n:
            if not self._in_action_tag:
                if text[i:].startswith("[ACTION:"):
                    self._in_action_tag = True
                    self._in_string = False
                    self._escape_next = False
                    self._bracket_depth = 1  # For '[' in '[ACTION:'
                    self._brace_depth = 0
                    i += len("[ACTION:")
                    continue

                potential_prefix = False
                for p_len in range(1, len("[ACTION:")):
                    prefix = "[ACTION:"[:p_len]
                    if text[i:] == prefix:
                        self._pending_prefix = text[i:]
                        potential_prefix = True
                        break
                if potential_prefix:
                    break

                output.append(text[i])
                i += 1
            else:
                ch = text[i]
                if self._in_string:
                    if self._escape_next:
                        self._escape_next = False
                    elif ch == '\\':
                        self._escape_next = True
                    elif ch == '"':
                        self._in_string = False
                else:
                    if ch == '"':
                        self._in_string = True
                        self._escape_next = False
                    elif ch == '{':
                        self._brace_depth += 1
                    elif ch == '}':
                        if self._brace_depth > 0:
                            self._brace_depth -= 1
                    elif ch == '[':
                        self._bracket_depth += 1
                    elif ch == ']':
                        if self._bracket_depth > 0:
                            self._bracket_depth -= 1
                        if self._bracket_depth <= 0 or (self._brace_depth == 0 and ch == ']'):
                            self._in_action_tag = False
                            self._in_string = False
                            self._escape_next = False
                            self._brace_depth = 0
                            self._bracket_depth = 0
                i += 1

        return "".join(output)

    def flush(self) -> str:
        res = self._pending_prefix
        self._pending_prefix = ""
        return res

