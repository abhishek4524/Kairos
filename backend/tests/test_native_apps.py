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
    """Test successful WhatsApp Desktop native send with unique contact resolved."""
    # Build mocks
    mock_app_inst = MagicMock()
    mock_app_class.return_value.connect.return_value = mock_app_inst
    
    mock_window = MagicMock()
    mock_app_inst.window.return_value = mock_window
    
    # Mock descendants
    mock_search = MockUIElement("Search or start new chat", "Edit")
    mock_contact = MockUIElement("Vansh Kumar\nLast message...", "ListItem")
    mock_msg_input = MockUIElement("Type a message", "Edit")
    mock_send = MockUIElement("Send", "Button")
    
    # Mock bubble that matches verification rules: contains "sent" and "hello test"
    mock_bubble = MockUIElement("sent: hello test message bubble", "ListItem")
    
    # We mock window.descendants to return our elements based on parameters
    def mock_descendants(control_type=None):
        if control_type == "Edit":
            return [mock_search, mock_msg_input]
        elif control_type == "ListItem":
            return [mock_contact, mock_bubble]
        elif control_type == "Button":
            return [mock_send]
        return []
        
    mock_window.descendants = mock_descendants

    # Execute tool (with security check bypassed by mock_guard)
    with patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True}):
        res = execute_tool("send_whatsapp_desktop_message", {"recipient": "Vansh", "message": "hello test"})
        
    assert res["success"] is True
    assert "sent to Vansh Kumar successfully" in res["message"]
    
    # Verify UIA actions occurred
    assert mock_search.clicked is True
    assert "Vansh" in mock_search.typed_keys
    assert mock_contact.clicked is True
    assert mock_msg_input.clicked is True
    assert "hello test" in mock_msg_input.typed_keys
    assert mock_send.clicked is True


@patch("platform.system", return_value="Windows")
@patch("os.startfile")
@patch("pywinauto.Application")
def test_whatsapp_native_ambiguous_contact(mock_app_class, mock_startfile, mock_platform):
    """Test multiple matches for contact returns list of matches for disambiguation."""
    mock_app_inst = MagicMock()
    mock_app_class.return_value.connect.return_value = mock_app_inst
    mock_window = MagicMock()
    mock_app_inst.window.return_value = mock_window
    
    mock_search = MockUIElement("Search", "Edit")
    # Multiple contacts matching "Vansh"
    mock_contact1 = MockUIElement("Vansh Kumar\nActive", "ListItem")
    mock_contact2 = MockUIElement("Vansh Sharma\nBusy", "ListItem")
    
    def mock_descendants(control_type=None):
        if control_type == "Edit":
            return [mock_search]
        elif control_type == "ListItem":
            return [mock_contact1, mock_contact2]
        return []
        
    mock_window.descendants = mock_descendants

    with patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True}):
        res = execute_tool("send_whatsapp_desktop_message", {"recipient": "Vansh", "message": "hello"})
        
    assert res["success"] is False
    assert res["error_type"] == "AMBIGUOUS_RECIPIENT"
    assert "Vansh Kumar" in res["matches"]
    assert "Vansh Sharma" in res["matches"]


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


def test_whatsapp_native_permissions_blocked_on_decline():
    """Verify tool is blocked if confirmation is requested and then user declines."""
    # First invocation should return requires_confirmation
    res = execute_tool("send_whatsapp_desktop_message", {"recipient": "Vansh Kumar", "message": "test message"})
    assert res.get("success") is False
    assert res.get("requires_confirmation") is True
    
    action_id = res.get("action_id")
    assert action_id is not None
    
    # Decline the pending action
    declined = confirm_pending_action(action_id, "no")
    assert declined["success"] is False
    assert "cancelled by user" in declined["message"]


@patch("agent_tools.native_apps.send_whatsapp_desktop_message")
def test_whatsapp_native_permissions_approved_flow(mock_send):
    """Verify tool executes only after user confirms with yes."""
    mock_send.return_value = {"success": True, "message": "Message sent!"}
    
    # Initiate tool call
    res = execute_tool("send_whatsapp_desktop_message", {"recipient": "Vansh Kumar", "message": "test message"})
    action_id = res.get("action_id")
    assert action_id is not None
    
    # Approve the action
    approved = confirm_pending_action(action_id, "yes")
    assert approved["success"] is True
    assert "Message sent!" in approved["message"]
    mock_send.assert_called_once_with("Vansh Kumar", "test message")
