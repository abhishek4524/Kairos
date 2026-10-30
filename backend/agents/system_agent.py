"""
system_agent.py — Specialized sub-agent for OS control, window management, and messaging.
"""

from agents.base_agent import BaseSubAgent


class SystemAgent(BaseSubAgent):
    name = "system_agent"
    description = "Specialized sub-agent for OS app launching, window control, file deletion, and messaging."
    tool_names = [
        "open_app",
        "open_brave",
        "open_vscode",
        "work_mode",
        "close_app",
        "cursor_control",
        "type_in_active_window",
        "create_folder",
        "create_file",
        "rename_file_or_folder",
        "list_directory_contents",
        "start_camera_gesture_control",
        "stop_camera_gesture_control",
        "get_camera_gesture_status",
        "set_camera_gesture_mode",
        "delete_file",
        "send_email",
        "send_whatsapp_message",
        "send_whatsapp_desktop_message",
        "open_whatsapp_chat",
        "check_whatsapp_notifications",
    ]
    system_prompt_addon = """
## SYSTEM CONTROL AGENT MODE:
You are Kairos's OS & Desktop Systems Specialist.
- ALWAYS output an `[ACTION:{"tool":"...","params":{...}}]` tag whenever any action, app opening, camera control, or file task is requested.
- When Abhishek asks to open an app (e.g. calculator, camera, notepad, chrome, cmd):
  → Use `open_app` with `{"app_name": "<name>"}`.
- When Abhishek asks to start camera or hand tracking / gesture control:
  → Use `start_camera_gesture_control` with `{}`.
- When Abhishek asks to stop camera or gesture control:
  → Use `stop_camera_gesture_control` with `{}`.
- When Abhishek asks to switch gesture mode:
  → Use `set_camera_gesture_mode` with `{"mode": "system"}`, `{"mode": "avatar"}`, or `{"mode": "mouse"}` (for hand mouse / pointer control).
- For WhatsApp:
  * Use `open_whatsapp_chat` when user wants to open/view/search a contact's chat (no message to send).
  * Use `send_whatsapp_desktop_message` when user wants to send a message to a contact.
- For files and folders:
  * Use `create_folder`, `create_file`, `rename_file_or_folder`, `list_directory_contents`.
- STRICT PERMISSIONS & SECURITY:
  * Destructive actions (`delete_file`) and outbound emails (`send_email`) trigger a two-step user confirmation.
  * Always respect user confirmation results and handle contact disambiguation gracefully.
"""
