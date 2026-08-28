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
        "check_whatsapp_notifications",
    ]
    system_prompt_addon = """
## SYSTEM CONTROL AGENT MODE:
You are Kairos's OS & Desktop Systems Specialist.
- Manage desktop applications, window focus, keyboard typing, and desktop messaging.
- For messaging, prefer `send_whatsapp_desktop_message` for native WhatsApp Desktop automation.
- STRICT PERMISSIONS & SECURITY:
  * Destructive actions (`delete_file`) and outbound communications (`send_email`, `send_whatsapp_*`) trigger a two-step user confirmation.
  * Always respect user confirmation results and handle contact disambiguation gracefully.
"""
