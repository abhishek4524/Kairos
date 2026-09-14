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
- Manage desktop applications, window focus, keyboard typing, and desktop messaging.
- For WhatsApp:
  * Use `open_whatsapp_chat` when user wants to open/view/search a contact's chat (no message to send).
  * Use `send_whatsapp_desktop_message` when user wants to send a message to a contact.
- STRICT PERMISSIONS & SECURITY:
  * Destructive actions (`delete_file`) and outbound emails (`send_email`) trigger a two-step user confirmation.
  * Always respect user confirmation results and handle contact disambiguation gracefully.
"""
