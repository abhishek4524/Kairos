"""
test_tool_executor.py — Unit tests for registered tools with mocked external drivers.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_tools.executor import execute_tool, confirm_pending_action
from agent_tools.registry import TOOLS_SCHEMA


def test_registered_tools_exist_in_schema():
    """Verify that all expected tool names exist in TOOLS_SCHEMA."""
    names = [t["function"]["name"] for t in TOOLS_SCHEMA]
    expected = [
        "navigate_to", "find_and_click", "type_into", "scroll_page",
        "extract_page_text", "go_back", "open_new_tab", "switch_tab",
        "open_youtube_in_brave", "youtube_search", "youtube_play_video", "youtube_control",
        "open_app", "close_app", "cursor_control", "open_vscode_and_write_code",
        "open_notepad_and_write_code", "write_and_run_sandbox_code", "work_mode"
    ]
    for exp in expected:
        assert exp in names


# ── Generic Browser Primitives Tests ──────────────────────────────────────────

def test_navigate_to_tool(mock_browser):
    res = execute_tool("navigate_to", {"url_or_search_query": "https://python.org"})
    assert res["success"] is True
    mock_browser["navigate_to"].assert_called_once_with("https://python.org")


def test_find_and_click_tool(mock_browser):
    res = execute_tool("find_and_click", {"description": "Documentation button"})
    assert res["success"] is True
    mock_browser["find_and_click"].assert_called_once_with("Documentation button")


def test_type_into_tool(mock_browser):
    res = execute_tool("type_into", {"description": "search box", "text": "asyncio", "press_enter": True})
    assert res["success"] is True
    mock_browser["type_into"].assert_called_once_with("search box", "asyncio", True)


def test_scroll_page_tool(mock_browser):
    res = execute_tool("scroll_page", {"direction": "down", "amount": 600})
    assert res["success"] is True
    mock_browser["scroll_page"].assert_called_once_with(direction="down", amount=600)


def test_extract_page_text_tool(mock_browser):
    res = execute_tool("extract_page_text", {"max_chars": 2000})
    assert res["success"] is True
    mock_browser["extract_page_text"].assert_called_once_with(2000)


def test_go_back_tool(mock_browser):
    res = execute_tool("go_back", {})
    assert res["success"] is True
    mock_browser["go_back"].assert_called_once()


def test_open_new_tab_tool(mock_browser):
    res = execute_tool("open_new_tab", {"url": "https://github.com"})
    assert res["success"] is True
    mock_browser["open_new_tab"].assert_called_once_with("https://github.com")


def test_switch_tab_tool(mock_browser):
    res = execute_tool("switch_tab", {"index_or_description": 2})
    assert res["success"] is True
    mock_browser["switch_tab"].assert_called_once_with(2)


# ── Legacy YouTube Shortcuts Tests ────────────────────────────────────────────

def test_youtube_tools(mock_browser):
    res_open = execute_tool("open_youtube_in_brave", {"query": "python tutorial"})
    assert res_open["success"] is True
    
    res_search = execute_tool("youtube_search", {"query": "fastapi"})
    assert res_search["success"] is True

    res_play = execute_tool("youtube_play_video", {"index": 1})
    assert res_play["success"] is True
    mock_browser["youtube_play_video"].assert_called_with(1)

    res_ctrl = execute_tool("youtube_control", {"action": "play_pause"})
    assert res_ctrl["success"] is True
    mock_browser["youtube_control"].assert_called_once_with("play_pause")


# ── Desktop & OS Tools Tests ──────────────────────────────────────────────────

@patch("config.platform_paths.launch_default_app", return_value=True)
@patch("subprocess.Popen")
def test_open_app_tool(mock_popen, mock_launch):
    res = execute_tool("open_app", {"app_name": "calc"})
    assert res["success"] is True


@patch("config.platform_paths.kill_process_by_name", return_value=True)
def test_close_app_tool(mock_kill):
    res = execute_tool("close_app", {"app_name": "calc"})
    assert res["success"] is True
    mock_kill.assert_called_once_with("calc")


@patch("agent_tools.executor._run_auto", return_value=True)
def test_cursor_control_tool(mock_run):
    res = execute_tool("cursor_control", {"action": "click", "x": 100, "y": 200})
    assert res["success"] is True
    mock_run.assert_called_once()


@patch("agent_tools.executor._run_auto", return_value=True)
def test_type_in_active_window_tool(mock_run):
    res = execute_tool("type_in_active_window", {"text": "Hello World"})
    assert res["success"] is True


@patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True})
@patch("subprocess.Popen")
def test_open_notepad_and_write_code_tool(mock_popen, mock_guard):
    res = execute_tool("open_notepad_and_write_code", {"filename": "test_note.py", "code": "print(1)"})
    assert res["success"] is True


@patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True})
@patch("subprocess.Popen")
def test_open_vscode_and_write_code_tool(mock_popen, mock_guard):
    res = execute_tool("open_vscode_and_write_code", {"filename": "test_script.py", "code": "x = 10"})
    assert res["success"] is True


@patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True})
def test_write_and_run_sandbox_code_tool(mock_guard):
    res = execute_tool("write_and_run_sandbox_code", {"language": "python", "code": "print('ok')"})
    assert res["success"] is True


    assert res["success"] is True


# ── Additional Coverage Tests for executor.py ──────────────────────────────────

import urllib.parse
import subprocess
from unittest.mock import patch, MagicMock
from agent_tools.permissions import PendingAction

# 1. Test _run_pyautogui_code / _run_auto subprocess success and error paths
@patch("subprocess.run")
@patch("config.platform_paths.get_venv_python_path", return_value="python")
def test_run_pyautogui_code_paths(mock_get_path, mock_run):
    from agent_tools.executor import _run_auto
    
    # Success path
    mock_run.return_value = MagicMock(returncode=0)
    assert _run_auto("pyautogui.click()") is True
    
    # Failure path
    mock_run.return_value = MagicMock(returncode=1)
    assert _run_auto("pyautogui.click()") is False
    
    # Exception/Timeout path
    mock_run.side_effect = subprocess.SubprocessError("Subprocess failed")
    assert _run_auto("pyautogui.click()") is False


# 2. Test confirm_pending_action
@patch("agent_tools.permissions.confirmation_mgr.validate_confirmation")
@patch("agent_tools.executor.execute_tool")
def test_confirm_pending_action_executor(mock_exec, mock_val):
    # Denied or invalid path
    mock_val.return_value = (False, None, "Invalid response")
    res = confirm_pending_action("action_123", "no")
    assert res["success"] is False
    assert "Invalid response" in res["message"]
    
    # Approved path
    mock_val.return_value = (True, PendingAction("action_123", "DESTRUCTIVE", "delete_file", {"filename": "test.txt"}, "Delete file", "Confirm deletion?"), "Approved")
    mock_exec.return_value = {"success": True, "message": "Deleted"}
    res = confirm_pending_action("action_123", "yes")
    assert res["success"] is True
    mock_exec.assert_called_once_with("delete_file", {"filename": "test.txt"}, confirmed_action_id="action_123")


# 3. Test delete_file (success, path resolution error)
@patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True})
@patch("agent_tools.permissions.resolve_secure_workspace_path")
@patch("agent_tools.permissions.move_to_trash")
def test_delete_file_tool(mock_trash, mock_resolve, mock_guard):
    # Invalid resolution
    mock_resolve.return_value = (False, "", "Traversal attempt blocked")
    res = execute_tool("delete_file", {"filename": "../../secret.txt"})
    assert res["success"] is False
    assert "Traversal attempt blocked" in res["message"]
    
    # Valid resolution & move to trash
    mock_resolve.return_value = (True, "C:\\workspace\\test.txt", "")
    mock_trash.return_value = (True, "Moved to trash successfully")
    res = execute_tool("delete_file", {"filename": "test.txt"})
    assert res["success"] is True
    assert "Moved to trash" in res["message"]


# 4. Test WhatsApp and Email drafting tools
@patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True})
@patch("agent_tools.browser.navigate_to")
def test_whatsapp_tools(mock_nav, mock_guard):
    mock_nav.return_value = {"success": True}
    res = execute_tool("send_whatsapp_message", {"recipient": "Abhishek", "message": "Hi!"})
    assert res["success"] is True
    
    res = execute_tool("check_whatsapp_notifications", {})
    assert res["success"] is True


@patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True})
@patch("config.platform_paths.launch_default_app", return_value=True)
def test_send_email_tool(mock_launch, mock_guard):
    res = execute_tool("send_email", {"recipient": "test@example.com", "subject": "Hello", "body": "Body"})
    assert res["success"] is True
    mock_launch.assert_called_once()


# 5. Cursor control action branches
@patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True})
@patch("agent_tools.executor._run_auto", return_value=True)
def test_cursor_control_various_actions(mock_run, mock_guard):
    for action in ["double_click", "right_click", "move", "type_text", "press_key"]:
        res = execute_tool("cursor_control", {"action": action, "x": 10, "y": 20, "text": "test", "key": "enter"})
        assert res["success"] is True
        
    # Unknown action
    res = execute_tool("cursor_control", {"action": "fly_to_moon"})
    assert res["success"] is False
    assert "Unknown cursor action" in res["message"]


# 6. App opening branches (Brave, VS Code failure, Text Editor, Unknown app failure)
@patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True})
@patch("agent_tools.executor._focus_brave")
@patch("agent_tools.executor._launch_brave")
def test_open_app_brave(mock_launch, mock_focus, mock_guard):
    res = execute_tool("open_app", {"app_name": "brave"})
    assert res["success"] is True
    mock_focus.assert_called_once()
    mock_launch.assert_called_once()


@patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True})
@patch("config.platform_paths.get_vscode_path", return_value="code")
@patch("subprocess.Popen", side_effect=Exception("Launch failed"))
def test_open_app_vscode_exception(mock_popen, mock_vscode_path, mock_guard):
    res = execute_tool("open_app", {"app_name": "vscode"})
    assert res["success"] is False
    assert "Could not open VS Code" in res["message"]


@patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True})
@patch("config.platform_paths.get_text_editor_command", return_value=["notepad"])
@patch("subprocess.Popen")
def test_open_app_text_editor(mock_popen, mock_editor_cmd, mock_guard):
    with patch("os.path.exists", return_value=True):
        res = execute_tool("open_app", {"app_name": "notepad"})
        assert res["success"] is True


@patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True})
@patch("shutil.which", return_value="/usr/bin/some_binary")
@patch("subprocess.Popen")
def test_open_app_shutil_which(mock_popen, mock_which, mock_guard):
    res = execute_tool("open_app", {"app_name": "some_binary"})
    assert res["success"] is True


@patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True})
@patch("shutil.which", return_value=None)
@patch("config.platform_paths.launch_default_app", return_value=False)
def test_open_app_not_found(mock_launch, mock_which, mock_guard):
    res = execute_tool("open_app", {"app_name": "non_existent_app"})
    assert res["success"] is False


# 7. App closing exception / unknown app failure
@patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True})
@patch("config.platform_paths.kill_process_by_name", return_value=False)
def test_close_app_failure(mock_kill, mock_guard):
    res = execute_tool("close_app", {"app_name": "non_existent_app"})
    assert res["success"] is False


# 8. Notepad & VS Code write errors
@patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True})
@patch("builtins.open", side_effect=Exception("File access denied"))
def test_write_code_tool_exceptions(mock_open, mock_guard):
    res = execute_tool("open_notepad_and_write_code", {"filename": "a.py", "code": "print()"})
    assert res["success"] is False
    assert "Editor error" in res["message"]

    res = execute_tool("open_vscode_and_write_code", {"filename": "a.py", "code": "print()"})
    assert res["success"] is False
    assert "VS Code error" in res["message"]


# 9. JSON extraction fallback testing
def test_try_fix_json_deeply_broken():
    from agent_tools.executor import extract_action
    # Deeply broken JSON that cannot be fixed
    assert extract_action('[ACTION:{"tool": "invalid" : : : : }') is None
    
    # Valid loose JSON that can be fixed
    fixed = extract_action('[ACTION:{"tool": "valid", "params": {}')
    assert fixed is not None
    assert fixed["tool"] == "valid"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


