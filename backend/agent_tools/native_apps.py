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


def send_whatsapp_desktop_message(recipient: str, message: str) -> Dict[str, Any]:
    """
    Sends a message to a specific contact via native WhatsApp Desktop application.
    Supports contact resolution, disambiguation, and verification.
    """
    system = platform.system()
    if system == "Windows":
        return send_whatsapp_desktop_message_windows(recipient, message)
    elif system == "Darwin":
        return send_whatsapp_desktop_message_macos(recipient, message)
    else:
        # Linux / other platforms fallback
        return {
            "success": False,
            "message": (
                "Native WhatsApp Desktop automation is not supported on Linux due to "
                "varying sandbox configurations (Snap/Flatpak). Please use the browser-based "
                "WhatsApp Web tool (send_whatsapp_message) instead."
            )
        }


def send_whatsapp_desktop_message_windows(recipient: str, message: str) -> Dict[str, Any]:
    """
    Windows implementation using pywinauto (UIA backend).
    """
    try:
        import pywinauto
        from pywinauto import Application
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
        # Launch using the registered URI protocol
        try:
            os.startfile("whatsapp:")
            # Wait for application window to spawn
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

    # 2. Locate the Search Box Edit control
    search_box = None
    try:
        # Look for edit controls with search-like properties
        for child in window.descendants(control_type="Edit"):
            name = child.element_info.name or ""
            if "search" in name.lower() or name == "Search":
                search_box = child
                break
        if not search_box:
            # Fallback to first edit control found
            edits = window.descendants(control_type="Edit")
            if edits:
                search_box = edits[0]
    except Exception as e:
        return {"success": False, "message": f"Error scanning UI tree for search box: {e}"}

    if not search_box:
        return {"success": False, "message": "Could not locate the search box in WhatsApp Desktop."}

    # Click search and type recipient
    try:
        search_box.click_input()
        # Clear existing text
        search_box.type_keys("^a{BACKSPACE}", set_foreground=False)
        search_box.type_keys(recipient, set_foreground=False)
    except Exception as e:
        return {"success": False, "message": f"Failed to type recipient in search box: {e}"}

    # Wait for results to filter
    time.sleep(1.2)

    # 3. Scan results for matches in the contacts list
    matches: List[Tuple[str, Any]] = []
    seen_names = set()

    try:
        # Search results list elements are typically ListItems
        for child in window.descendants(control_type="ListItem"):
            name = child.element_info.name
            if name and recipient.lower() in name.lower():
                # Clean multi-line UWP list items to get just the header (contact name)
                clean_name = name.split("\n")[0].strip()
                if clean_name not in seen_names:
                    seen_names.add(clean_name)
                    matches.append((clean_name, child))

        # If no ListItems, check Button elements
        if not matches:
            for child in window.descendants(control_type="Button"):
                name = child.element_info.name
                if name and recipient.lower() in name.lower() and name != "Send":
                    clean_name = name.split("\n")[0].strip()
                    if clean_name not in seen_names:
                        seen_names.add(clean_name)
                        matches.append((clean_name, child))
    except Exception as e:
        return {"success": False, "message": f"Error scanning search results: {e}"}

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
        contact_element.click_input()
    except Exception as e:
        return {"success": False, "message": f"Failed to select contact '{resolved_name}': {e}"}

    time.sleep(0.5)

    # 4. Locate the message input box
    message_input = None
    try:
        for child in window.descendants(control_type="Edit"):
            name = child.element_info.name or ""
            if "type a message" in name.lower() or "write a message" in name.lower() or "message" in name.lower():
                message_input = child
                break
        
        # Fallback to Document type (sometimes used in updated UWP apps)
        if not message_input:
            for child in window.descendants(control_type="Document"):
                message_input = child
                break

        # Final fallback to last available Edit control
        if not message_input:
            edits = window.descendants(control_type="Edit")
            if edits:
                message_input = edits[-1]
    except Exception as e:
        return {"success": False, "message": f"Error scanning UI tree for message input: {e}"}

    if not message_input:
        return {"success": False, "message": "Could not locate message input field."}

    # Type message
    try:
        message_input.click_input()
        message_input.type_keys(message, with_spaces=True, set_foreground=False)
    except Exception as e:
        return {"success": False, "message": f"Failed to type message text: {e}"}

    # 5. Click the Send button
    send_btn = None
    try:
        for child in window.descendants(control_type="Button"):
            name = child.element_info.name or ""
            if name.lower() == "send" or "send" in name.lower():
                send_btn = child
                break
    except Exception:
        pass

    try:
        if send_btn:
            send_btn.click_input()
        else:
            # Fallback to typing Enter inside message field
            message_input.type_keys("{ENTER}", set_foreground=False)
    except Exception as e:
        return {"success": False, "message": f"Failed to click send button or press enter: {e}"}

    time.sleep(1.0)

    # 6. Verification Step: Read back the last message bubble
    last_message = ""
    try:
        messages = []
        for child in window.descendants(control_type="ListItem"):
            name = child.element_info.name
            # Message elements usually contain sent/read receipts or time info
            if name and any(receipt in name.lower() for receipt in ["sent", "read", "delivered", "delivered status"]):
                messages.append(name)
        if messages:
            last_message = messages[-1]
    except Exception:
        pass

    # Lightweight verification check
    if last_message and message.lower()[:15] in last_message.lower():
        return {
            "success": True,
            "message": f"Message sent to {resolved_name} successfully (verified via native UI readback)."
        }
    else:
        # Default success if UI match fails but send executed without exception
        return {
            "success": True,
            "message": f"Message sent to {resolved_name} (unable to verify via last bubble text)."
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
