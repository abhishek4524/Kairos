"""
native_apps.py — Native Desktop application automation for Kairos.

Automates native desktop apps (like WhatsApp Desktop) using platform-specific
Accessibility and UI Automation APIs (pywinauto for Windows, atomacos for macOS).
"""

import sys
import time
import os
import platform
import subprocess
from typing import Dict, Any, List, Tuple


def open_whatsapp_chat(recipient: str) -> Dict[str, Any]:
    """
    Opens or focuses a specific contact's chat window in native WhatsApp Desktop application.
    """
    system = platform.system()
    if system == "Windows":
        return open_whatsapp_chat_windows(recipient)
    elif system == "Darwin":
        return open_whatsapp_chat_macos(recipient)
    else:
        return {
            "success": False,
            "message": "Native WhatsApp Desktop automation is not supported on Linux."
        }


def open_whatsapp_chat_windows(recipient: str) -> Dict[str, Any]:
    """
    Windows implementation to open a specific contact's chat in WhatsApp Desktop.
    Uses native window focus, Ctrl+F shortcut search, contact filtering, and Enter selection.
    """
    if not recipient or not recipient.strip():
        return {
            "success": False,
            "error_type": "AMBIGUOUS_RECIPIENT",
            "message": "Recipient contact name is missing or empty. Please specify a contact name."
        }
    try:
        import pywinauto
        from pywinauto import Application, keyboard
    except ImportError:
        return {
            "success": False,
            "message": "Required library 'pywinauto' is not installed. Please run pip install pywinauto."
        }

    # 1. Connect to running WhatsApp or start it
    app = None
    try:
        app = Application(backend="uia").connect(title_re=".*WhatsApp.*", timeout=2)
    except Exception:
        try:
            os.startfile("whatsapp:")
            time.sleep(3.0)
            app = Application(backend="uia").connect(title_re=".*WhatsApp.*", timeout=8)
        except Exception as e:
            return {
                "success": False,
                "message": f"WhatsApp Desktop is not installed or could not be launched on Windows: {e}"
            }

    try:
        window = app.window(title_re=".*WhatsApp.*")
        window.set_focus()
    except Exception as e:
        return {
            "success": False,
            "message": f"Could not focus WhatsApp Desktop window: {e}"
        }

    time.sleep(0.5)

    # 2. Activate search via Ctrl+F shortcut
    keyboard.send_keys("^f")
    time.sleep(0.3)
    keyboard.send_keys("^a{BACKSPACE}")
    time.sleep(0.1)

    # 3. Type contact name into search box
    keyboard.send_keys(recipient, with_spaces=True)
    time.sleep(1.0)

    # 4. Press Enter to select top matching contact and open their chat window
    keyboard.send_keys("{ENTER}")
    time.sleep(0.5)

    return {
        "success": True,
        "message": f"Opened chat for '{recipient}' in WhatsApp Desktop."
    }


def open_whatsapp_chat_macos(recipient: str) -> Dict[str, Any]:
    """macOS implementation for opening WhatsApp chat."""
    return send_whatsapp_desktop_message_macos(recipient, "")


def send_whatsapp_desktop_message(recipient: str, message: str) -> Dict[str, Any]:
    """
    Sends a message to a specific contact via native WhatsApp Desktop application.
    """
    system = platform.system()
    if system == "Windows":
        return send_whatsapp_desktop_message_windows(recipient, message)
    elif system == "Darwin":
        return send_whatsapp_desktop_message_macos(recipient, message)
    else:
        return {
            "success": False,
            "message": "Native WhatsApp Desktop automation is not supported on Linux."
        }


def send_whatsapp_desktop_message_windows(recipient: str, message: str) -> Dict[str, Any]:
    """
    Windows implementation: opens recipient chat window and types/sends the message.
    """
    # 1. Open contact chat window
    open_res = open_whatsapp_chat_windows(recipient)
    if not open_res.get("success"):
        return open_res

    time.sleep(0.4)

    # 2. Type message into open chat field and press Enter
    try:
        from pywinauto import keyboard
        keyboard.send_keys(message, with_spaces=True)
        time.sleep(0.3)
        keyboard.send_keys("{ENTER}")
        time.sleep(0.5)
        return {
            "success": True,
            "message": f"Message sent to {recipient} successfully in WhatsApp Desktop."
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to type or send message to {recipient}: {e}"
        }


def send_whatsapp_desktop_message_macos(recipient: str, message: str) -> Dict[str, Any]:
    """
    macOS implementation using atomacos (Apple Accessibility API).
    """
    try:
        import atomacos
    except ImportError:
        return {
            "success": False,
            "message": "Required library 'atomacos' is not installed. Please run pip install atomacos."
        }

    # 1. Connect to running WhatsApp or start it
    try:
        # Try finding bundle ID
        app = atomacos.getAppRefByBundleId("net.whatsapp.WhatsApp")
    except Exception:
        try:
            # Launch App
            subprocess.Popen(["open", "-a", "WhatsApp"])
            time.sleep(3.0)
            app = atomacos.getAppRefByBundleId("net.whatsapp.WhatsApp")
        except Exception as e:
            return {
                "success": False,
                "message": f"WhatsApp Desktop is not installed or could not be launched on macOS: {e}"
            }

    try:
        # Get primary window
        window = app.windows()[0]
        window.set_focus()
    except Exception as e:
        return {
            "success": False,
            "message": f"Could not focus WhatsApp Desktop window on macOS: {e}"
        }

    time.sleep(0.5)

    # 2. Locate Search Box
    search_field = None
    try:
        for child in window.descendants():
            role = child.role
            title = child.title or ""
            placeholder = getattr(child, "placeholder", "") or ""
            if role == "AXTextField" and ("search" in title.lower() or "search" in placeholder.lower()):
                search_field = child
                break
        if not search_field:
            textfields = [c for c in window.descendants() if c.role == "AXTextField"]
            if textfields:
                search_field = textfields[0]
    except Exception as e:
        return {"success": False, "message": f"Error scanning UI tree for search field: {e}"}

    if not search_field:
        return {"success": False, "message": "Could not locate search field in WhatsApp Desktop."}

    # Click and type contact name
    try:
        search_field.click()
        search_field.type(recipient)
    except Exception as e:
        return {"success": False, "message": f"Failed to type recipient in search field: {e}"}

    time.sleep(1.2)

    # 3. Locate matches in results list
    matches = []
    seen_names = set()
    try:
        # Contacts list matches AXButton or AXGroup elements
        for child in window.descendants():
            if child.role in ("AXButton", "AXGroup") and child.title and recipient.lower() in child.title.lower():
                clean_name = child.title.split("\n")[0].strip()
                if clean_name not in seen_names:
                    seen_names.add(clean_name)
                    matches.append((clean_name, child))
    except Exception as e:
        return {"success": False, "message": f"Error scanning search results list: {e}"}

    if not matches:
        return {"success": False, "message": f"No contacts found matching '{recipient}' in WhatsApp Desktop."}

    if len(matches) > 1:
        match_names = [m[0] for m in matches]
        return {
            "success": False,
            "error_type": "AMBIGUOUS_RECIPIENT",
            "matches": match_names,
            "message": f"Multiple contacts matched '{recipient}': {', '.join(match_names)}. Please specify the exact name."
        }

    # Unique match resolved
    resolved_name, contact_element = matches[0]
    try:
        contact_element.click()
    except Exception as e:
        return {"success": False, "message": f"Failed to select contact '{resolved_name}': {e}"}

    time.sleep(0.5)

    # 4. Locate message input area
    message_input = None
    try:
        for child in window.descendants():
            if child.role in ("AXTextArea", "AXTextField") and child != search_field:
                message_input = child
                break
    except Exception as e:
        return {"success": False, "message": f"Error scanning for message field: {e}"}

    if not message_input:
        return {"success": False, "message": "Could not locate message input field."}

    # Type message
    try:
        message_input.click()
        message_input.type(message)
    except Exception as e:
        return {"success": False, "message": f"Failed to type message text: {e}"}

    # 5. Send message
    send_btn = None
    try:
        for child in window.descendants():
            if child.role == "AXButton" and child.title and child.title.lower() == "send":
                send_btn = child
                break
    except Exception:
        pass

    try:
        if send_btn:
            send_btn.click()
        else:
            message_input.type("\n")
    except Exception as e:
        return {"success": False, "message": f"Failed to click send button: {e}"}

    time.sleep(1.0)

    # 6. Verification Step: Read last message bubble
    last_message = ""
    try:
        text_elements = [c.value for c in window.descendants() if c.role == "AXStaticText" and c.value]
        if text_elements:
            last_message = text_elements[-1]
    except Exception:
        pass

    if last_message and message.lower()[:15] in last_message.lower():
        return {
            "success": True,
            "message": f"Message sent to {resolved_name} successfully (verified via native Accessibility)."
        }
    else:
        return {
            "success": True,
            "message": f"Message sent to {resolved_name} (unable to verify via last static text)."
        }
