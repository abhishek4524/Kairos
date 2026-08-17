"""
executor.py — Executes agentic desktop tool calls on Windows.

Called directly from main.py when a [ACTION:{...}] tag is detected
in the LLM stream. Each tool runs via subprocess/webbrowser so the
FastAPI process stays responsive.
"""

import os
import re
import json
import subprocess
import webbrowser
import tempfile
import urllib.parse
from typing import Optional

# ── App name → Windows executable mapping ────────────────────────────────────
APP_MAP = {
    "chrome":          ["cmd", "/c", "start", "chrome"],
    "google":          ["cmd", "/c", "start", "chrome"],
    "google chrome":   ["cmd", "/c", "start", "chrome"],
    "brave":           ["cmd", "/c", "start", "brave"],
    "brave browser":   ["cmd", "/c", "start", "brave"],
    "firefox":         ["cmd", "/c", "start", "firefox"],
    "edge":            ["cmd", "/c", "start", "msedge"],
    "microsoft edge":  ["cmd", "/c", "start", "msedge"],
    "youtube":         ["cmd", "/c", "start", "chrome", "https://www.youtube.com"],
    "spotify":         ["cmd", "/c", "start", "spotify"],
    "notepad":         ["notepad.exe"],
    "calc":            ["calc.exe"],
    "calculator":      ["calc.exe"],
    "code":            ["code"],
    "vscode":          ["code"],
    "vs code":         ["code"],
    "visual studio code": ["code"],
    "discord":         ["cmd", "/c", "start", "discord"],
    "terminal":        ["cmd", "/c", "start", "cmd"],
    "cmd":             ["cmd", "/c", "start", "cmd"],
    "command prompt":  ["cmd", "/c", "start", "cmd"],
    "powershell":      ["cmd", "/c", "start", "powershell"],
    "file explorer":   ["explorer.exe"],
    "explorer":        ["explorer.exe"],
    "windows explorer": ["explorer.exe"],
    "this pc":         ["explorer.exe"],
    "paint":           ["mspaint.exe"],
    "vlc":             ["vlc"],
    "whatsapp":        ["cmd", "/c", "start", "whatsapp"],
    "telegram":        ["cmd", "/c", "start", "telegram"],
    "word":            ["cmd", "/c", "start", "winword"],
    "excel":           ["cmd", "/c", "start", "excel"],
    "powerpoint":      ["cmd", "/c", "start", "powerpnt"],
    "zoom":            ["cmd", "/c", "start", "zoom"],
    "task manager":    ["taskmgr.exe"],
    "settings":        ["cmd", "/c", "start", "ms-settings:"],
    "control panel":   ["control"],
    "snipping tool":   ["SnippingTool.exe"],
}


def execute_tool(tool_name: str, params: dict) -> dict:
    """
    Execute a desktop tool. Returns {"success": bool, "message": str}.
    All execution is fire-and-forget (non-blocking).
    """
    try:
        if tool_name == "open_app":
            return _open_app(params.get("app_name", ""))

        elif tool_name == "close_app":
            return _close_app(params.get("app_name", ""))

        elif tool_name == "search_and_play_youtube":
            return _search_youtube(params.get("query", ""))

        elif tool_name == "toggle_room_light":
            state = params.get("state", "toggle")
            return {"success": True, "message": f"Desk lamp set to {state}."}

        elif tool_name == "sit_on_chair":
            return {"success": True, "message": "Sitting on chair."}

        elif tool_name == "stand_up":
            return {"success": True, "message": "Standing up."}

        elif tool_name == "read_book":
            return {"success": True, "message": "Walking to bookshelf to read."}

        elif tool_name == "put_book_down":
            return {"success": True, "message": "Putting book down."}

        elif tool_name == "jump":
            return {"success": True, "message": "Jumping!"}

        elif tool_name == "open_vscode_and_write_code":
            return _open_vscode_write(params.get("filename", "script.py"), params.get("code", ""))

        elif tool_name == "write_and_run_sandbox_code":
            # This is handled on the frontend side via WebSocket message
            return {"success": True, "message": "Sandbox code will be written via frontend."}

        elif tool_name == "check_whatsapp_notifications":
            # Sensitive — only runs after frontend confirmation; opens WhatsApp Web
            webbrowser.open("https://web.whatsapp.com")
            return {"success": True, "message": "Opened WhatsApp Web."}

        else:
            return {"success": False, "message": f"Unknown tool: {tool_name}"}

    except Exception as e:
        return {"success": False, "message": str(e)}


def _open_app(app_name: str) -> dict:
    """Open a Windows application by name."""
    key = app_name.lower().strip()
    cmd = APP_MAP.get(key)

    # Fuzzy partial match — e.g. "Brave Browser" -> "brave browser" -> "brave"
    if not cmd:
        for map_key in APP_MAP:
            if map_key in key or key in map_key:
                cmd = APP_MAP[map_key]
                break

    if cmd:
        subprocess.Popen(cmd, shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
        return {"success": True, "message": f"Opened {app_name}."}

    # Fallback: try os.startfile or direct exe call
    try:
        os.startfile(key)
        return {"success": True, "message": f"Opened {app_name} via startfile."}
    except Exception:
        pass

    # Last resort: use Windows 'start' command
    try:
        subprocess.Popen(["cmd", "/c", "start", key], shell=False,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        return {"success": True, "message": f"Launched {app_name} via start command."}
    except Exception as e:
        return {"success": False, "message": f"Could not open {app_name}: {e}"}


CLOSE_MAP = {
    "calc": ["CalculatorApp.exe", "calc.exe"],
    "calculator": ["CalculatorApp.exe", "calc.exe"],
    "notepad": ["notepad.exe"],
    "chrome": ["chrome.exe"],
    "brave": ["brave.exe"],
    "code": ["Code.exe"],
    "vscode": ["Code.exe"],
    "vs code": ["Code.exe"],
    "spotify": ["Spotify.exe"],
    "discord": ["Discord.exe"],
    "cmd": ["cmd.exe"],
    "terminal": ["WindowsTerminal.exe", "cmd.exe"],
    "powershell": ["powershell.exe"],
}

def _close_app(app_name: str) -> dict:
    """Close/terminate a Windows application by name."""
    key = app_name.lower().strip()
    proc_list = CLOSE_MAP.get(key)
    if not proc_list:
        for map_key in CLOSE_MAP:
            if map_key in key or key in map_key:
                proc_list = CLOSE_MAP[map_key]
                break

    if not proc_list:
        proc_list = [f"{key}.exe"]

    success = False
    for proc in proc_list:
        try:
            res = subprocess.run(
                ["taskkill", "/IM", proc, "/F"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if res.returncode == 0:
                success = True
        except Exception:
            pass

    if success:
        return {"success": True, "message": f"Closed {app_name}."}
    return {"success": False, "message": f"Could not find or close {app_name}."}


def _search_youtube(query: str) -> dict:
    """Open a YouTube search in the default browser."""
    if not query:
        url = "https://www.youtube.com"
    else:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.youtube.com/results?search_query={encoded}"
    
    # Try opening via Windows start command first, then fallback to webbrowser
    try:
        subprocess.Popen(["cmd", "/c", "start", "", url], shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        webbrowser.open(url)
    return {"success": True, "message": f"Opened YouTube search for: {query}"}


def _open_vscode_write(filename: str, code: str) -> dict:
    """Write code to a temp file and open it in VS Code."""
    try:
        temp_dir = tempfile.mkdtemp(prefix="kavya_code_")
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        subprocess.Popen(["code", filepath], shell=False,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        return {"success": True, "message": f"Opened {filename} in VS Code."}
    except Exception as e:
        return {"success": False, "message": f"VS Code error: {e}"}


# ── Action tag extraction ─────────────────────────────────────────────────────
_ACTION_RE = re.compile(r'\[ACTION:(\{.*?\})\]', re.DOTALL)

def _try_fix_json(raw: str) -> Optional[dict]:
    """Attempt to parse potentially truncated JSON by adding missing closing braces."""
    for extra in ["", "}", "}}", "\"}", "\"}}"]:
        try:
            return json.loads(raw + extra)
        except json.JSONDecodeError:
            continue
    return None

def extract_action(text: str) -> Optional[dict]:
    """Extract the first [ACTION:{...}] tag from LLM text. Returns parsed dict or None."""
    m = _ACTION_RE.search(text)
    if not m:
        # Also try a looser match in case closing ] is missing
        loose = re.search(r'\[ACTION:(\{[^\]]*)', text, re.DOTALL)
        if not loose:
            return None
        return _try_fix_json(loose.group(1))
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return _try_fix_json(m.group(1))

def strip_action_tag(text: str) -> str:
    """Remove all [ACTION:{...}] tags from text (for TTS / display)."""
    cleaned = _ACTION_RE.sub("", text)
    # Also strip any loose [ACTION:... that didn't close properly
    cleaned = re.sub(r'\[ACTION:\{[^\]]*', "", cleaned)
    return cleaned.strip()
