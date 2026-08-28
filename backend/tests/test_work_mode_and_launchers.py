"""
test_work_mode_and_launchers.py — Unit test suite for Work Mode (Chrome CDP) and Standalone Launchers.

Tests:
1. work_mode opens all 4 configured sites + VS Code successfully.
2. work_mode reports partial failure clearly if one site fails to load.
3. open_brave and open_vscode work standalone.
4. Missing Chrome / Missing Brave / Missing VS Code errors are reported clearly without crashing.
5. work_mode_sites configuration customization via env vars.
6. Multi-browser CDP isolation (Brave default port 9222 vs Chrome default port 9223).
"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import platform_paths
from config import work_mode_sites
from agent_tools import browser
from agent_tools import executor
from agent_tools.registry import TOOLS_SCHEMA, format_system_tools_prompt, TOOL_AGENT_MAP
from agent_tools import permissions


class TestWorkModeAndLaunchers(unittest.TestCase):

    def setUp(self):
        # Clear any environment overrides before each test
        for var in ["KAIROS_CHROME_PATH", "KAIROS_BRAVE_PATH", "KAIROS_VSCODE_PATH",
                    "KAIROS_WORK_MODE_SITES", "KAIROS_DEFAULT_WORKSPACE",
                    "KAIROS_CDP_PORT", "KAIROS_CHROME_CDP_PORT"]:
            if var in os.environ:
                del os.environ[var]

    def test_chrome_path_resolution(self):
        """Test Google Chrome path resolution with environment override and standard detection."""
        # 1. Test override
        os.environ["KAIROS_CHROME_PATH"] = sys.executable
        chrome_p = platform_paths.get_chrome_path()
        self.assertEqual(chrome_p, sys.executable)
        del os.environ["KAIROS_CHROME_PATH"]

        # 2. Check diagnostics includes chrome
        diag = platform_paths.check_required_executables()
        self.assertIn("chrome", diag)
        self.assertIn("Google Chrome", diag["chrome"]["name"])
        self.assertEqual(diag["chrome"]["env_var"], "KAIROS_CHROME_PATH")

    def test_work_mode_sites_config_and_customization(self):
        """Test default work mode sites and environment variable override."""
        sites = work_mode_sites.get_work_mode_sites()
        self.assertIsInstance(sites, list)
        self.assertEqual(len(sites), 4)
        names = [s["name"] for s in sites]
        self.assertIn("GitHub", names)
        self.assertIn("LeetCode", names)
        self.assertIn("Gmail", names)
        self.assertIn("ChatGPT", names)

        # Test custom override
        custom = [
            {"name": "StackOverflow", "url": "https://stackoverflow.com", "expected_keyword": "overflow"}
        ]
        os.environ["KAIROS_WORK_MODE_SITES"] = json.dumps(custom)
        custom_sites = work_mode_sites.get_work_mode_sites()
        self.assertEqual(len(custom_sites), 1)
        self.assertEqual(custom_sites[0]["name"], "StackOverflow")
        del os.environ["KAIROS_WORK_MODE_SITES"]

        # Test workspace path
        ws = work_mode_sites.get_default_workspace()
        self.assertTrue(ws.endswith("KairosWorkspace") or "KairosWorkspace" in ws)

        os.environ["KAIROS_DEFAULT_WORKSPACE"] = os.path.join(os.getcwd(), "test_workspace")
        self.assertEqual(work_mode_sites.get_default_workspace(), os.path.abspath(os.path.join(os.getcwd(), "test_workspace")))
        del os.environ["KAIROS_DEFAULT_WORKSPACE"]

    def test_cdp_port_isolation(self):
        """Verify Brave and Chrome managers use separate ports and profile directories."""
        brave_mgr = browser.get_browser_manager("brave")
        chrome_mgr = browser.get_browser_manager("chrome")

        self.assertNotEqual(brave_mgr.cdp_port, chrome_mgr.cdp_port)
        self.assertEqual(brave_mgr.cdp_port, 9222)
        self.assertEqual(chrome_mgr.cdp_port, 9223)
        self.assertEqual(brave_mgr.browser_name, "brave")
        self.assertEqual(chrome_mgr.browser_name, "chrome")

    @patch("agent_tools.browser.get_browser_manager")
    @patch("config.platform_paths.get_chrome_path")
    @patch("config.platform_paths.get_vscode_path")
    @patch("subprocess.Popen")
    def test_work_mode_success_all_sites_and_vscode(self, mock_popen, mock_vscode, mock_chrome, mock_get_mgr):
        """Test work_mode succeeds when all 4 sites load and VS Code opens."""
        mock_chrome.return_value = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        mock_vscode.return_value = "C:\\Users\\user\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe"

        # Mock Chrome Manager and Page
        mock_mgr = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_page.url = "https://github.com"
        mock_page.title.return_value = "GitHub: Let's build from here"
        mock_context.pages = [mock_page]
        mock_context.new_page.return_value = mock_page
        mock_mgr._context = mock_context
        mock_mgr._ensure_connected_worker.return_value = (True, "Connected")
        
        # When run_sync is called with _worker_work_mode, execute the worker logic
        def fake_run_sync(func, *args, **kwargs):
            return func(*args, **kwargs)

        mock_mgr.run_sync.side_effect = fake_run_sync
        mock_get_mgr.return_value = mock_mgr

        result = executor.execute_tool("work_mode", {})
        self.assertTrue(result.get("success"), f"Expected success: {result}")
        self.assertEqual(len(result.get("loaded_tabs", [])), 4)
        self.assertEqual(len(result.get("failed_tabs", [])), 0)
        self.assertIn("Work mode activated", result.get("message", ""))
        self.assertTrue(mock_popen.called)

    @patch("agent_tools.browser.get_browser_manager")
    @patch("config.platform_paths.get_chrome_path")
    @patch("config.platform_paths.get_vscode_path")
    @patch("subprocess.Popen")
    def test_work_mode_partial_failure_reporting(self, mock_popen, mock_vscode, mock_chrome, mock_get_mgr):
        """Test work_mode reports partial failure clearly if 1 site fails to load."""
        mock_chrome.return_value = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        mock_vscode.return_value = "C:\\Users\\user\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe"

        mock_mgr = MagicMock()
        mock_context = MagicMock()
        
        # Site 0, 1, 2 succeed, Site 3 (ChatGPT) fails
        call_count = [0]
        def fake_new_page():
            p = MagicMock()
            call_count[0] += 1
            if call_count[0] == 4:
                p.goto.side_effect = Exception("ERR_CONNECTION_TIMED_OUT")
            else:
                p.url = "https://example.com"
                p.title.return_value = "Loaded"
            return p

        mock_context.pages = []
        mock_context.new_page.side_effect = fake_new_page
        mock_mgr._context = mock_context
        mock_mgr._ensure_connected_worker.return_value = (True, "Connected")
        mock_mgr.run_sync.side_effect = lambda f, *args, **kwargs: f(*args, **kwargs)
        mock_get_mgr.return_value = mock_mgr

        result = executor.execute_tool("work_mode", {})
        self.assertTrue(result.get("success"))
        self.assertTrue(result.get("partial_failure"))
        self.assertEqual(len(result.get("loaded_tabs", [])), 3)
        self.assertEqual(len(result.get("failed_tabs", [])), 1)
        self.assertIn("partially activated", result.get("message", ""))
        self.assertIn("ChatGPT", result["failed_tabs"][0]["name"])

    @patch("config.platform_paths.get_chrome_path")
    def test_work_mode_chrome_not_installed_error(self, mock_chrome):
        """Test work_mode reports clear error if Google Chrome is not installed."""
        mock_chrome.return_value = None

        result = executor.execute_tool("work_mode", {})
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error_type"), "CHROME_NOT_FOUND")
        self.assertIn("Google Chrome is not installed", result.get("message", ""))
        self.assertIn("KAIROS_CHROME_PATH", result.get("message", ""))

    @patch("config.platform_paths.get_brave_path")
    @patch("agent_tools.executor._focus_brave")
    @patch("agent_tools.executor._launch_brave")
    def test_open_brave_standalone(self, mock_launch, mock_focus, mock_brave):
        """Test open_brave standalone tool execution."""
        mock_brave.return_value = "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe"
        with patch("os.path.exists", return_value=True):
            result = executor.execute_tool("open_brave", {})
            self.assertTrue(result.get("success"))
            self.assertIn("Opened Brave", result.get("message", ""))
            self.assertTrue(mock_focus.called)
            self.assertTrue(mock_launch.called)

    @patch("config.platform_paths.get_brave_path")
    def test_open_brave_not_found_error(self, mock_brave):
        """Test open_brave reports clear error if Brave is not installed."""
        mock_brave.return_value = None
        result = executor.execute_tool("open_brave", {})
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error_type"), "BRAVE_NOT_FOUND")
        self.assertIn("Brave browser is not installed", result.get("message", ""))

    @patch("config.platform_paths.get_vscode_path")
    @patch("subprocess.Popen")
    def test_open_vscode_standalone(self, mock_popen, mock_vscode):
        """Test open_vscode standalone tool execution."""
        mock_vscode.return_value = "C:\\Microsoft VS Code\\Code.exe"
        with patch("os.path.exists", return_value=True):
            result = executor.execute_tool("open_vscode", {})
            self.assertTrue(result.get("success"))
            self.assertIn("Opened VS Code", result.get("message", ""))
            self.assertTrue(mock_popen.called)

    @patch("config.platform_paths.get_vscode_path")
    def test_open_vscode_not_found_error(self, mock_vscode):
        """Test open_vscode reports clear error if VS Code is not installed."""
        mock_vscode.return_value = None
        result = executor.execute_tool("open_vscode", {})
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error_type"), "VSCODE_NOT_FOUND")
        self.assertIn("Visual Studio Code is not installed", result.get("message", ""))

    def test_registry_schemas_and_ownership(self):
        """Verify registry schemas and sub-agent ownership map for new tools."""
        tool_names = [t["function"]["name"] for t in TOOLS_SCHEMA]
        self.assertIn("open_brave", tool_names)
        self.assertIn("open_vscode", tool_names)
        self.assertIn("work_mode", tool_names)

        self.assertEqual(TOOL_AGENT_MAP.get("open_brave"), "browsing_agent")
        self.assertEqual(TOOL_AGENT_MAP.get("open_vscode"), "coding_agent")
        self.assertEqual(TOOL_AGENT_MAP.get("work_mode"), "browsing_agent")

        prompt = format_system_tools_prompt()
        self.assertIn("open_brave", prompt)
        self.assertIn("open_vscode", prompt)
        self.assertIn("work_mode", prompt)

        self.assertIn("open_brave", permissions.PERMITTED_TOOLS)
        self.assertIn("open_vscode", permissions.PERMITTED_TOOLS)
        self.assertIn("work_mode", permissions.PERMITTED_TOOLS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
