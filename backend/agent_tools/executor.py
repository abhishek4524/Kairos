"""
executor.py — Desktop & browser automation tools for Kairos on Windows.

Key design: pyautogui runs in VENV Python subprocess (guaranteed to work).
This avoids pyautogui import failures in the FastAPI server process.
"""

import os
import re
import json
import subprocess
import tempfile
import time
import threading
import urllib.parse
from typing import Optional

# ── Venv Python path — guaranteed to have pyautogui installed ─────────────────
VENV_PYTHON = r"f:\Personal Assistant\backend\venv\Scripts\python.exe"

# ── Brave browser absolute path ────────────────────────────────────────────────
BRAVE_EXE = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
if not os.path.exists(BRAVE_EXE):
    for _p in [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "BraveSoftware",
                     "Brave-Browser", "Application", "brave.exe"),
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    ]:
        if os.path.exists(_p):
            BRAVE_EXE = _p
            break


def _run_auto(code: str, timeout: int = 12) -> bool:
    """
    Execute pyautogui automation code in the venv Python subprocess.
    Prepend standard imports/settings so callers just pass the body.
    """
    full_code = (
        "import pyautogui, time, subprocess\n"
        "pyautogui.FAILSAFE = False\n"
        "pyautogui.PAUSE = 0.05\n"
        + code
    )
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                        delete=False, encoding="utf-8") as f:
            f.write(full_code)
            fname = f.name
        r = subprocess.run(
            [VENV_PYTHON, fname],
            capture_output=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return r.returncode == 0
    except Exception as e:
        print(f"[AUTO] Subprocess error: {e}")
        return False
    finally:
        try:
            os.unlink(fname)
        except Exception:
            pass


def _launch_brave(url=""):
    """Open a URL strictly in Brave — never Chrome or default browser."""
    args = [BRAVE_EXE]
    if url:
        args.append(url)
    subprocess.Popen(args, creationflags=subprocess.CREATE_NO_WINDOW)


def _focus_brave():
    """Bring any open Brave window to the foreground."""
    try:
        ps = "(New-Object -ComObject WScript.Shell).AppActivate('Brave')"
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, timeout=2,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        pass


# App map — brave always uses full path
APP_MAP = {
    "brave":              [BRAVE_EXE],
    "brave browser":      [BRAVE_EXE],
    "chrome":             ["cmd", "/c", "start", "chrome"],
    "google":             ["cmd", "/c", "start", "chrome"],
    "google chrome":      ["cmd", "/c", "start", "chrome"],
    "firefox":            ["cmd", "/c", "start", "firefox"],
    "edge":               ["cmd", "/c", "start", "msedge"],
    "microsoft edge":     ["cmd", "/c", "start", "msedge"],
    "youtube":            [BRAVE_EXE, "https://www.youtube.com"],
    "spotify":            ["cmd", "/c", "start", "spotify"],
    "notepad":            ["notepad.exe"],
    "calc":               ["calc.exe"],
    "calculator":         ["calc.exe"],
    "code":               ["code"],
    "vscode":             ["code"],
    "vs code":            ["code"],
    "visual studio code": ["code"],
    "discord":            ["cmd", "/c", "start", "discord"],
    "terminal":           ["cmd", "/c", "start", "cmd"],
    "cmd":                ["cmd", "/c", "start", "cmd"],
    "command prompt":     ["cmd", "/c", "start", "cmd"],
    "powershell":         ["cmd", "/c", "start", "powershell"],
    "file explorer":      ["explorer.exe"],
    "explorer":           ["explorer.exe"],
    "paint":              ["mspaint.exe"],
    "vlc":                ["vlc"],
    "whatsapp":           ["cmd", "/c", "start", "whatsapp"],
    "telegram":           ["cmd", "/c", "start", "telegram"],
    "task manager":       ["taskmgr.exe"],
    "settings":           ["cmd", "/c", "start", "ms-settings:"],
}


def execute_tool(tool_name: str, params: dict) -> dict:
    try:
        if tool_name == "open_app":
            return _open_app(params.get("app_name", "brave"))
        elif tool_name == "close_app":
            return _close_app(params.get("app_name", ""))
        elif tool_name in ("open_youtube_in_brave", "search_and_play_youtube"):
            return _open_youtube_in_brave(params.get("query", ""))
        elif tool_name == "youtube_search":
            return _youtube_search(params.get("query", ""))
        elif tool_name == "youtube_play_video":
            return _youtube_play_video(int(params.get("index", 1)))
        elif tool_name == "scroll_page":
            return _scroll_page(params.get("direction", "down"), int(params.get("amount", 500)))
        elif tool_name == "youtube_control":
            return _youtube_control(params.get("action", "play_pause"))
        elif tool_name == "cursor_control":
            return _cursor_control(
                action=params.get("action", "click"),
                x=params.get("x"), y=params.get("y"),
                text=params.get("text"), key=params.get("key"),
            )
        elif tool_name == "type_in_active_window":
            return _type_in_active_window(params.get("text", ""))
        elif tool_name == "open_notepad_and_write_code":
            return _open_notepad_write(params.get("filename", "code.py"), params.get("code", ""))
        elif tool_name == "open_vscode_and_write_code":
            return _open_vscode_write(params.get("filename", "solution.py"), params.get("code", ""))
        elif tool_name == "write_and_run_sandbox_code":
            return {"success": True, "message": "Sandbox code ready."}
        elif tool_name == "work_mode":
            return _work_mode()
        else:
            return {"success": False, "message": f"Unknown tool: {tool_name}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ── YouTube / Brave ────────────────────────────────────────────────────────────

def _open_youtube_in_brave(query=""):
    """Open YouTube ONLY in Brave. No Chrome fallback ever."""
    url = "https://www.youtube.com"
    if query:
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
    _focus_brave()
    time.sleep(0.2)
    _launch_brave(url)
    return {"success": True, "message": "Opened YouTube in Brave" + (f" — search: {query}" if query else "") + "."}


def _youtube_search(query):
    """Search YouTube in Brave only."""
    if not query:
        return _open_youtube_in_brave("")
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
    _focus_brave()
    time.sleep(0.2)
    _launch_brave(url)
    return {"success": True, "message": f"Searching YouTube for '{query}' in Brave."}


def _youtube_play_video(index=1):
    """
    Play Nth YouTube video. Strategy:
    1. Focus Brave, wait 2.5s for page load.
    2. Use pyautogui (via subprocess) to click at the position of the Nth video.
    YouTube search result layout on 1920x1080 (approx):
      - First result y: ~270px, each result: ~145px gap, thumbnail x: ~245px
    """
    index = max(1, index)

    def _play_seq():
        _focus_brave()
        time.sleep(2.5)  # Wait for YouTube page to fully load

        code = f"""
w, h = pyautogui.size()
# Thumbnail column is about 14% from left
x = int(w * 0.14)
# First result at ~25% height, each result ~14% of height apart
y = int(h * 0.25 + ({index} - 1) * h * 0.145)
# Scroll to top first to normalize position
pyautogui.hotkey('ctrl', 'Home')
time.sleep(0.5)
pyautogui.moveTo(x, y, duration=0.3)
pyautogui.click()
time.sleep(0.4)
# Press Enter as fallback in case focus landed on element
pyautogui.press('enter')
"""
        _run_auto(code.strip())

    threading.Thread(target=_play_seq, daemon=True).start()
    return {"success": True, "message": f"Clicking video #{index} on YouTube."}


def _scroll_page(direction="down", amount=500):
    """Scroll active Brave window using venv pyautogui subprocess."""
    _focus_brave()
    time.sleep(0.2)
    ticks = -(amount // 50) if direction.lower() == "down" else (amount // 50)
    code = f"pyautogui.scroll({ticks})"
    ok = _run_auto(code)
    if ok:
        return {"success": True, "message": f"Scrolled {direction}."}
    return {"success": False, "message": "Scroll subprocess failed."}


def _youtube_control(action):
    """Send YouTube keyboard shortcuts via subprocess automation."""
    _focus_brave()
    time.sleep(0.15)

    act = action.lower().strip()
    mapping = {
        "play_pause": "k", "play": "k", "pause": "k", "toggle": "k",
        "mute": "m", "unmute": "m",
        "fullscreen": "f", "full_screen": "f",
        "seek_forward": "l", "forward": "l",
        "seek_backward": "j", "rewind": "j",
        "restart": "0", "beginning": "0",
    }

    if act in mapping:
        key = mapping[act]
        code = f"""
w, h = pyautogui.size()
pyautogui.click(w // 2, h // 2)
time.sleep(0.1)
pyautogui.press('{key}')
"""
        _run_auto(code.strip())
        return {"success": True, "message": f"YouTube: {action}."}

    elif act in ("volume_up", "louder"):
        code = """
w, h = pyautogui.size()
pyautogui.click(w // 2, h // 2)
time.sleep(0.1)
for _ in range(3): pyautogui.press('up')
"""
        _run_auto(code.strip())
        return {"success": True, "message": "Volume up."}

    elif act in ("volume_down", "quieter"):
        code = """
w, h = pyautogui.size()
pyautogui.click(w // 2, h // 2)
time.sleep(0.1)
for _ in range(3): pyautogui.press('down')
"""
        _run_auto(code.strip())
        return {"success": True, "message": "Volume down."}

    elif act in ("next_video", "next"):
        code = """
w, h = pyautogui.size()
pyautogui.click(w // 2, h // 2)
time.sleep(0.1)
pyautogui.hotkey('shift', 'n')
"""
        _run_auto(code.strip())
        return {"success": True, "message": "Next video."}

    return {"success": False, "message": f"Unknown YouTube action: {action}"}


def _cursor_control(action, x=None, y=None, text=None, key=None):
    """Mouse and keyboard automation via subprocess."""
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
    """Type text into whatever window is currently active/focused."""
    if not text:
        return {"success": False, "message": "No text provided."}
    safe_text = text.replace("\\", "\\\\").replace('"', '\\"').replace('\n', '\\n')
    code = f"""
time.sleep(0.3)
pyautogui.write("{safe_text}", interval=0.04)
"""
    ok = _run_auto(code.strip())
    return {"success": ok, "message": f"Typed text in active window."}


# ── App management ─────────────────────────────────────────────────────────────

def _open_app(app_name):
    key = app_name.lower().strip()
    if key in ("brave", "brave browser"):
        _focus_brave()
        time.sleep(0.1)
        _launch_brave()
        return {"success": True, "message": "Opened Brave Browser."}

    cmd = APP_MAP.get(key)
    if not cmd:
        for mk in APP_MAP:
            if mk in key or key in mk:
                cmd = APP_MAP[mk]
                break

    if cmd:
        subprocess.Popen(cmd, shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
        return {"success": True, "message": f"Opened {app_name}."}

    try:
        os.startfile(key)
        return {"success": True, "message": f"Opened {app_name}."}
    except Exception:
        pass

    try:
        subprocess.Popen(["cmd", "/c", "start", key], shell=False,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        return {"success": True, "message": f"Launched {app_name}."}
    except Exception as e:
        return {"success": False, "message": f"Could not open {app_name}: {e}"}


CLOSE_MAP = {
    "calc":       ["CalculatorApp.exe", "calc.exe"],
    "calculator": ["CalculatorApp.exe", "calc.exe"],
    "notepad":    ["notepad.exe"],
    "chrome":     ["chrome.exe"],
    "brave":      ["brave.exe"],
    "code":       ["Code.exe"],
    "vscode":     ["Code.exe"],
    "vs code":    ["Code.exe"],
    "spotify":    ["Spotify.exe"],
    "discord":    ["Discord.exe"],
    "cmd":        ["cmd.exe"],
    "terminal":   ["WindowsTerminal.exe", "cmd.exe"],
    "powershell": ["powershell.exe"],
}


def _close_app(app_name):
    key = app_name.lower().strip()
    proc_list = CLOSE_MAP.get(key)
    if not proc_list:
        for mk in CLOSE_MAP:
            if mk in key or key in mk:
                proc_list = CLOSE_MAP[mk]
                break
    if not proc_list:
        proc_list = [f"{key}.exe"]
    success = False
    for proc in proc_list:
        try:
            r = subprocess.run(["taskkill", "/IM", proc, "/F"],
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if r.returncode == 0:
                success = True
        except Exception:
            pass
    if success:
        return {"success": True, "message": f"Closed {app_name}."}
    return {"success": False, "message": f"Could not close {app_name}."}


# ── Work Mode ──────────────────────────────────────────────────────────────────
WORK_MODE_URLS = [
    "https://github.com/abhishek4524",
    "https://leetcode.com/u/abhishek_kumar_20/",
    "https://mail.google.com/mail/u/0/#inbox",
    "https://chatgpt.com/",
]


def _work_mode():
    def _launch():
        for url in WORK_MODE_URLS:
            try:
                subprocess.Popen(["cmd", "/c", "start", "chrome", url],
                                 shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception:
                pass
            time.sleep(0.8)
        time.sleep(0.5)
        try:
            subprocess.Popen(["code"], shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            pass
        time.sleep(0.5)
        _launch_brave()
    threading.Thread(target=_launch, daemon=True).start()
    return {"success": True, "message": "Work mode activated."}


def _open_notepad_write(filename="code.py", code=""):
    """Create a temporary file with the given code and immediately open it in Notepad."""
    try:
        temp_dir = tempfile.mkdtemp(prefix="kairos_note_")
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        subprocess.Popen(["notepad.exe", filepath], shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
        return {"success": True, "message": f"Opened Notepad with {filename}."}
    except Exception as e:
        return {"success": False, "message": f"Notepad error: {e}"}


def _open_vscode_write(filename, code):
    try:
        temp_dir = tempfile.mkdtemp(prefix="kairos_code_")
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        subprocess.Popen(["code", filepath], shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
        return {"success": True, "message": f"Opened {filename} in VS Code."}
    except Exception as e:
        return {"success": False, "message": f"VS Code error: {e}"}


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
