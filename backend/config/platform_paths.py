"""
platform_paths.py — Cross-platform executable and path resolution for Kairos.

Handles OS detection (Windows, macOS, Linux), environment variable overrides,
and provides robust resolvers for Brave, VS Code, Python venv, text editors,
app focus, and process termination across operating systems.
"""

import os
import sys
import platform
import shutil
import subprocess
from typing import Optional, List, Dict, Any

# ── OS Detection ──────────────────────────────────────────────────────────────
SYSTEM = platform.system()
IS_WINDOWS = SYSTEM == "Windows"
IS_MACOS = SYSTEM == "Darwin"
IS_LINUX = SYSTEM == "Linux"

# Safe Windows subprocess flag (avoids crashing on macOS/Linux)
NO_WINDOW_FLAGS = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0

# Base backend directory
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KAIROS_DIR = BACKEND_DIR


# ── Brave Browser Resolution ──────────────────────────────────────────────────
def get_brave_path() -> Optional[str]:
    """
    Resolves the Brave executable path across operating systems.
    Priority:
      1. KAIROS_BRAVE_PATH environment variable override
      2. OS-specific standard installation locations
      3. System PATH lookup
    """
    # 1. Environment variable override
    env_override = os.environ.get("KAIROS_BRAVE_PATH")
    if env_override:
        clean_override = env_override.strip().strip('"\'')
        if not (os.path.exists(clean_override) or shutil.which(clean_override)):
            print(f"[PlatformPaths] Warning: KAIROS_BRAVE_PATH set to '{env_override}' but file not found.")
        return clean_override

    # 2. Windows resolution
    if IS_WINDOWS:
        candidates = [
            os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                         "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                         "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
        ]
        for path in candidates:
            if path and os.path.exists(path):
                return path
        which_brave = shutil.which("brave.exe") or shutil.which("brave")
        if which_brave:
            return which_brave

    # 3. macOS resolution
    elif IS_MACOS:
        candidates = [
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            os.path.expanduser("~/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        which_brave = shutil.which("brave") or shutil.which("brave-browser")
        if which_brave:
            return which_brave

    # 4. Linux resolution
    elif IS_LINUX:
        which_brave = shutil.which("brave-browser") or shutil.which("brave")
        if which_brave:
            return which_brave
        candidates = [
            "/usr/bin/brave-browser",
            "/opt/brave.com/brave/brave",
            "/usr/bin/brave",
            "/snap/bin/brave",
            os.path.expanduser("~/.local/bin/brave-browser"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path

    return None


# ── Google Chrome Resolution ──────────────────────────────────────────────────
def get_chrome_path() -> Optional[str]:
    """
    Resolves the Google Chrome executable path across operating systems.
    Priority:
      1. KAIROS_CHROME_PATH environment variable override
      2. OS-specific standard installation locations
      3. System PATH lookup
    """
    # 1. Environment variable override
    env_override = os.environ.get("KAIROS_CHROME_PATH")
    if env_override:
        clean_override = env_override.strip().strip('"\'')
        if not (os.path.exists(clean_override) or shutil.which(clean_override)):
            print(f"[PlatformPaths] Warning: KAIROS_CHROME_PATH set to '{env_override}' but file not found.")
        return clean_override

    # 2. Windows resolution
    if IS_WINDOWS:
        candidates = [
            os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                         "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                         "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         "Google", "Chrome", "Application", "chrome.exe"),
        ]
        for path in candidates:
            if path and os.path.exists(path):
                return path
        which_chrome = shutil.which("chrome.exe") or shutil.which("chrome")
        if which_chrome:
            return which_chrome

    # 3. macOS resolution
    elif IS_MACOS:
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        which_chrome = shutil.which("google-chrome") or shutil.which("chrome")
        if which_chrome:
            return which_chrome

    # 4. Linux resolution
    elif IS_LINUX:
        which_chrome = shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chrome")
        if which_chrome:
            return which_chrome
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/opt/google/chrome/chrome",
            "/usr/bin/chrome",
            os.path.expanduser("~/.local/bin/google-chrome"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path

    return None


# ── VS Code Resolution ────────────────────────────────────────────────────────
def get_vscode_path() -> Optional[str]:
    """
    Resolves the VS Code executable command/path across operating systems.
    Priority:
      1. KAIROS_VSCODE_PATH environment variable override
      2. System PATH lookup (`code` command)
      3. OS-specific standard installation locations
    """
    env_override = os.environ.get("KAIROS_VSCODE_PATH")
    if env_override:
        clean_override = env_override.strip().strip('"\'')
        if not (os.path.exists(clean_override) or shutil.which(clean_override)):
            print(f"[PlatformPaths] Warning: KAIROS_VSCODE_PATH set to '{env_override}' but file not found.")
        return clean_override

    which_code = shutil.which("code")
    if which_code:
        return which_code

    if IS_WINDOWS:
        candidates = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "Code.exe"),
            os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), "Microsoft VS Code", "Code.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"), "Microsoft VS Code", "Code.exe"),
        ]
        for path in candidates:
            if path and os.path.exists(path):
                return path

    elif IS_MACOS:
        candidates = [
            "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
            os.path.expanduser("~/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path

    elif IS_LINUX:
        candidates = ["/usr/bin/code", "/snap/bin/code", "/usr/share/code/bin/code"]
        for path in candidates:
            if os.path.exists(path):
                return path

    return "code"  # fallback string for standard shell invocation


# ── Python Venv Resolution ────────────────────────────────────────────────────
def get_venv_python_path() -> str:
    """
    Resolves Python interpreter path dynamically without hardcoded drive letters.
    """
    env_override = os.environ.get("KAIROS_PYTHON_PATH")
    if env_override and os.path.exists(env_override):
        return env_override

    # Check local backend/venv
    if IS_WINDOWS:
        local_venv = os.path.join(BACKEND_DIR, "venv", "Scripts", "python.exe")
    else:
        local_venv = os.path.join(BACKEND_DIR, "venv", "bin", "python")

    if os.path.exists(local_venv):
        return local_venv

    # Fallback to the current running Python executable
    return sys.executable


# ── Text Editor (Notepad / TextEdit / Gedit) Resolution ────────────────────────
def get_text_editor_command(file_path: str) -> List[str]:
    """
    Returns a cross-platform command list to open a text/code file in the OS editor.
    """
    if IS_WINDOWS:
        return ["notepad.exe", file_path]
    elif IS_MACOS:
        return ["open", "-e", file_path]
    elif IS_LINUX:
        for editor in ["gedit", "kate", "xed", "mousepad", "nano"]:
            if shutil.which(editor):
                return [editor, file_path]
        return ["xdg-open", file_path]
    return [sys.executable, file_path]


# ── Window Focus & Application Activation ─────────────────────────────────────
def focus_application(app_name: str = "Brave") -> bool:
    """
    Brings an open application window to focus across operating systems.
    """
    try:
        if IS_WINDOWS:
            ps = f"(New-Object -ComObject WScript.Shell).AppActivate('{app_name}')"
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, timeout=2,
                creationflags=NO_WINDOW_FLAGS,
            )
            return True
        elif IS_MACOS:
            script = f'tell application "{app_name}" to activate'
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, timeout=2
            )
            return True
        elif IS_LINUX:
            if shutil.which("wmctrl"):
                subprocess.run(["wmctrl", "-a", app_name], capture_output=True, timeout=2)
                return True
            elif shutil.which("xdotool"):
                subprocess.run(["xdotool", "search", "--name", app_name, "windowactivate"], capture_output=True, timeout=2)
                return True
    except Exception:
        pass
    return False


# ── OS Default Application Launcher ───────────────────────────────────────────
def launch_default_app(target: str) -> bool:
    """
    Opens a URL, file, or protocol in the default OS handler cross-platform.
    """
    try:
        if IS_WINDOWS:
            if hasattr(os, "startfile"):
                os.startfile(target)
                return True
            subprocess.Popen(["cmd", "/c", "start", "", target],
                             creationflags=NO_WINDOW_FLAGS)
            return True
        elif IS_MACOS:
            subprocess.Popen(["open", target])
            return True
        elif IS_LINUX:
            subprocess.Popen(["xdg-open", target])
            return True
    except Exception as e:
        print(f"[PlatformPaths] Failed to launch '{target}': {e}")
    return False


# ── Process Termination ───────────────────────────────────────────────────────
def kill_process_by_name(proc_name: str) -> bool:
    """
    Terminates a process by name cross-platform (taskkill on Windows, pkill/killall on Unix).
    """
    try:
        if IS_WINDOWS:
            proc = proc_name if proc_name.endswith(".exe") else f"{proc_name}.exe"
            r = subprocess.run(["taskkill", "/IM", proc, "/F"],
                               capture_output=True, creationflags=NO_WINDOW_FLAGS)
            return r.returncode == 0
        else:
            clean_name = proc_name.replace(".exe", "")
            if shutil.which("pkill"):
                r = subprocess.run(["pkill", "-f", clean_name], capture_output=True)
                return r.returncode == 0
            elif shutil.which("killall"):
                r = subprocess.run(["killall", clean_name], capture_output=True)
                return r.returncode == 0
    except Exception:
        pass
    return False


# ── Executable Diagnostics ────────────────────────────────────────────────────
def check_required_executables() -> Dict[str, Dict[str, Any]]:
    """
    Diagnostic checker to verify required executables at startup.
    Returns status and help text for any missing executables.
    """
    brave_path = get_brave_path()
    chrome_path = get_chrome_path()
    vscode_path = get_vscode_path()
    python_path = get_venv_python_path()

    results = {
        "brave": {
            "name": "Brave Browser",
            "found": brave_path is not None and (os.path.exists(brave_path) or shutil.which(brave_path) is not None),
            "path": brave_path,
            "env_var": "KAIROS_BRAVE_PATH",
            "help": "Set KAIROS_BRAVE_PATH in backend/.env with the full path to your Brave executable."
        },
        "chrome": {
            "name": "Google Chrome",
            "found": chrome_path is not None and (os.path.exists(chrome_path) or shutil.which(chrome_path) is not None),
            "path": chrome_path,
            "env_var": "KAIROS_CHROME_PATH",
            "help": "Set KAIROS_CHROME_PATH in backend/.env with the full path to your Chrome executable."
        },
        "vscode": {
            "name": "Visual Studio Code",
            "found": vscode_path is not None and (os.path.exists(vscode_path) or shutil.which(vscode_path) is not None),
            "path": vscode_path,
            "env_var": "KAIROS_VSCODE_PATH",
            "help": "Set KAIROS_VSCODE_PATH in backend/.env or ensure 'code' is in your system PATH."
        },
        "python": {
            "name": "Python Environment",
            "found": os.path.exists(python_path),
            "path": python_path,
            "env_var": "KAIROS_PYTHON_PATH",
            "help": "Ensure Python / venv is installed or set KAIROS_PYTHON_PATH in backend/.env."
        }
    }
    return results
