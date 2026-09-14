"""
test_native_apps.py — Unit tests for native WhatsApp Desktop UI automation and security flow.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Inject mock modules for UIA dependencies before any importing occurs
sys.modules["pywinauto"] = MagicMock()
sys.modules["pywinauto.Application"] = MagicMock()
sys.modules["atomacos"] = MagicMock()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_tools.executor import execute_tool, confirm_pending_action
from agent_tools.permissions import confirmation_mgr


# ── Mocking Helper for Windows pywinauto UI automation tree ───────────────────

class MockElementInfo:
    def __init__(self, name):
        self.name = name


class MockUIElement:
    def __init__(self, name, control_type="ListItem"):
        self.element_info = MockElementInfo(name)
        self.control_type = control_type
        self.clicked = False
        self.typed_keys = []

    def texts(self):
        return [self.element_info.name]

    def click_input(self):
        self.clicked = True

    def type_keys(self, keys, with_spaces=True, set_foreground=False):
        self.typed_keys.append(keys)


# ── Tests ──────────────────────────────────────────────────────────────────────

@patch("platform.system", return_value="Windows")
@patch("os.startfile")
@patch("pywinauto.Application")
def test_whatsapp_native_send_success(mock_app_class, mock_startfile, mock_platform):
    """Test successful WhatsApp Desktop native send with keyboard-driven flow."""
    # Build mocks
    mock_app_inst = MagicMock()
    mock_app_class.return_value.connect.return_value = mock_app_inst
    
    mock_window = MagicMock()
    mock_app_inst.window.return_value = mock_window

    # Mock pywinauto.keyboard.send_keys (used by the new keyboard-driven approach)
    with patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True}):
        with patch("pywinauto.keyboard") as mock_kb:
            res = execute_tool("send_whatsapp_desktop_message", {"recipient": "Vansh", "message": "hello test"})
        
    assert res["success"] is True
    assert "Vansh" in res["message"]


@patch("platform.system", return_value="Windows")
@patch("os.startfile")
@patch("pywinauto.Application")
def test_whatsapp_native_open_chat(mock_app_class, mock_startfile, mock_platform):
    """Test opening a contact's chat window in WhatsApp Desktop."""
    mock_app_inst = MagicMock()
    mock_app_class.return_value.connect.return_value = mock_app_inst
    mock_window = MagicMock()
    mock_app_inst.window.return_value = mock_window

    with patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True}):
        with patch("pywinauto.keyboard") as mock_kb:
            res = execute_tool("open_whatsapp_chat", {"recipient": "Akhil Dondal"})
        
    assert res["success"] is True
    assert "Akhil Dondal" in res["message"]


@patch("platform.system", return_value="Windows")
@patch("os.startfile")
@patch("pywinauto.Application")
def test_whatsapp_native_app_not_installed(mock_app_class, mock_startfile, mock_platform):
    """Test when application fails to connect/launch, returning a clear error."""
    # Mock connection failure
    mock_app_class.return_value.connect.side_effect = Exception("Not found")
    # Mock launch failure
    mock_startfile.side_effect = Exception("Protocol whatsapp not registered")
    
    with patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True}):
        res = execute_tool("send_whatsapp_desktop_message", {"recipient": "Vansh", "message": "hello"})
        
    assert res["success"] is False
    assert "not installed or could not be launched" in res["message"]


@patch("platform.system", return_value="Windows")
@patch("os.startfile")
@patch("pywinauto.Application")
def test_whatsapp_native_send_executes_directly(mock_app_class, mock_startfile, mock_platform):
    """Verify send_whatsapp_desktop_message executes directly without confirmation (SAFE tier)."""
    mock_app_inst = MagicMock()
    mock_app_class.return_value.connect.return_value = mock_app_inst
    mock_window = MagicMock()
    mock_app_inst.window.return_value = mock_window

    with patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True}):
        with patch("pywinauto.keyboard") as mock_kb:
            res = execute_tool("send_whatsapp_desktop_message", {"recipient": "Vansh Kumar", "message": "test message"})

    # Should succeed directly without requiring confirmation
    assert res["success"] is True
    assert "Vansh Kumar" in res["message"]


@patch("agent_tools.native_apps.open_whatsapp_chat")
def test_whatsapp_open_chat_tool_routing(mock_open_chat):
    """Verify open_whatsapp_chat is routed correctly through executor."""
    mock_open_chat.return_value = {"success": True, "message": "Opened chat for 'Akhil Dondal' in WhatsApp Desktop."}

    with patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True}):
        res = execute_tool("open_whatsapp_chat", {"recipient": "Akhil Dondal"})

    assert res["success"] is True
    assert "Akhil Dondal" in res["message"]
    mock_open_chat.assert_called_once_with("Akhil Dondal")
