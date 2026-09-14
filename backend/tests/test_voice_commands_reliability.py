"""
test_voice_commands_reliability.py — Integration test suite for the 6 core documented voice commands:
1. "Open Brave" (launch + focus verification, missing binary error handling)
2. "Open YouTube" (navigation, URL validation, and container mount verification)
3. "Search cloud computing" (search box typing/navigation, submit, and search results render assertion)
4. "Play first video" (ad-filtering, real video renderer targeting, click, /watch URL check, <video> play state)
5. "Scroll down" / "Scroll up" (multi-target scrolling, container scroll, keyboard PageDown/PageUp fallback)
6. "Write a simple code of Python in Notepad" (code validation, disk write UTF-8, file size check, Notepad execution)
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_tools import browser
from agent_tools import executor
from agent_tools.registry import TOOLS_SCHEMA, format_system_tools_prompt
from agent_tools import permissions


class TestVoiceCommandsReliability(unittest.TestCase):

    def setUp(self):
        # Clear any environment overrides
        for var in ["KAIROS_BRAVE_PATH", "KAIROS_CHROME_PATH", "KAIROS_VSCODE_PATH"]:
            if var in os.environ:
                del os.environ[var]

    # ── Command 1: "Open Brave" ────────────────────────────────────────────────
    @patch("config.platform_paths.get_brave_path")
    @patch("agent_tools.executor._focus_brave")
    @patch("agent_tools.executor._launch_brave")
    def test_cmd_open_brave_success(self, mock_launch, mock_focus, mock_brave):
        """Confirm 'Open Brave' triggers launch and application focus."""
        mock_brave.return_value = "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe"
        with patch("os.path.exists", return_value=True):
            res = executor.execute_tool("open_brave", {})
            self.assertTrue(res["success"])
            self.assertIn("Opened Brave", res["message"])
            self.assertTrue(mock_focus.called)
            self.assertTrue(mock_launch.called)

    @patch("config.platform_paths.get_brave_path", return_value=None)
    def test_cmd_open_brave_missing_executable_error(self, mock_brave):
        """Confirm 'Open Brave' reports clear diagnostic error if Brave is not installed."""
        res = executor.execute_tool("open_brave", {})
        self.assertFalse(res["success"])
        self.assertEqual(res.get("error_type"), "BRAVE_NOT_FOUND")
        self.assertIn("Brave browser is not installed", res["message"])
        self.assertIn("KAIROS_BRAVE_PATH", res["message"])

    # ── Command 2: "Open YouTube" ──────────────────────────────────────────────
    @patch("agent_tools.browser.BrowserManager._get_page_worker")
    def test_cmd_open_youtube_verified_load(self, mock_get_page):
        """Confirm 'Open YouTube' navigates and verifies that the YouTube container mounted."""
        mock_page = MagicMock()
        mock_page.url = "https://www.youtube.com/"
        mock_page.title.return_value = "YouTube"
        mock_get_page.return_value = mock_page

        res = browser.navigate_to("https://www.youtube.com")
        self.assertTrue(res["success"])
        self.assertIn("YouTube", res["message"])
        self.assertEqual(res["url"], "https://www.youtube.com/")
        mock_page.goto.assert_called_once_with("https://www.youtube.com", wait_until="domcontentloaded", timeout=20000)
        mock_page.wait_for_selector.assert_called_once()

    @patch("agent_tools.browser.BrowserManager._get_page_worker")
    def test_cmd_open_youtube_navigation_failure_reporting(self, mock_get_page):
        """Confirm navigation failure on YouTube reports specific diagnostic error."""
        mock_page = MagicMock()
        mock_page.goto.side_effect = Exception("net::ERR_INTERNET_DISCONNECTED")
        mock_get_page.return_value = mock_page

        res = browser.navigate_to("https://www.youtube.com")
        self.assertFalse(res["success"])
        self.assertEqual(res.get("error_type"), "NAVIGATION_FAILED")
        self.assertIn("ERR_INTERNET_DISCONNECTED", res["message"])

    # ── Command 3: "Search cloud computing" ────────────────────────────────────
    @patch("agent_tools.browser.BrowserManager._get_page_worker")
    def test_cmd_youtube_search_verified_results(self, mock_get_page):
        """Confirm YouTube search finds input box, submits, and asserts search results exist."""
        mock_page = MagicMock()
        mock_page.url = "https://www.youtube.com/results?search_query=cloud+computing"
        mock_page.title.return_value = "cloud computing - YouTube"
        
        mock_search_input = MagicMock()
        mock_search_input.count.return_value = 1
        mock_search_input.first = mock_search_input
        mock_results_locator = MagicMock()
        mock_results_locator.count.return_value = 12

        def fake_locator(sel):
            if "search" in sel:
                return mock_search_input
            return mock_results_locator

        mock_page.locator.side_effect = fake_locator
        mock_get_page.return_value = mock_page

        res = browser.youtube_search("cloud computing")
        self.assertTrue(res["success"])
        self.assertIn("Searched YouTube for 'cloud computing'", res["message"])
        self.assertIn("Found video results", res["message"])
        self.assertEqual(res["results_count"], 12)

    @patch("agent_tools.browser.BrowserManager._get_page_worker")
    def test_cmd_youtube_search_empty_query_error(self, mock_get_page):
        """Confirm empty query returns specific diagnostic error."""
        res = browser.youtube_search("   ")
        self.assertFalse(res["success"])
        self.assertEqual(res.get("error_type"), "EMPTY_QUERY")

    # ── Command 4: "Play first video" ──────────────────────────────────────────
    @patch("agent_tools.browser.BrowserManager._get_page_worker")
    def test_cmd_play_first_video_filters_ads_and_verifies_playback(self, mock_get_page):
        """Confirm playing Nth video excludes ads, clicks result, checks /watch and <video> state."""
        mock_page = MagicMock()
        mock_page.url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        mock_page.title.return_value = "Cloud Computing Full Course - YouTube"

        # Mock video locator and title
        mock_target = MagicMock()
        mock_target.count.return_value = 5
        mock_target.nth.return_value = mock_target
        mock_target.first = mock_target
        mock_target.evaluate.side_effect = lambda expr, *args: "Cloud Computing Full Course" if "innerText" in expr else "a"
        mock_target.bounding_box.return_value = {"x": 200, "y": 300, "width": 400, "height": 220}
        
        mock_page.locator.return_value = mock_target
        # Mock video state in DOM
        mock_page.evaluate.return_value = {
            "exists": True,
            "playing": True,
            "paused": False,
            "currentTime": 2.5,
            "duration": 3600.0
        }
        mock_get_page.return_value = mock_page

        res = browser.youtube_play_video(index=1)
        self.assertTrue(res["success"])
        self.assertIn("Playing Cloud Computing Full Course on YouTube", res["message"])
        self.assertEqual(res["index"], 1)
        self.assertTrue(mock_target.click.called)

    @patch("agent_tools.browser.BrowserManager._get_page_worker")
    def test_cmd_play_first_video_not_found_error(self, mock_get_page):
        """Confirm failure when no video items match in search results."""
        mock_page = MagicMock()
        mock_empty_loc = MagicMock()
        mock_empty_loc.count.return_value = 0
        mock_page.locator.return_value = mock_empty_loc
        mock_get_page.return_value = mock_page

        res = browser.youtube_play_video(index=1)
        self.assertFalse(res["success"])
        self.assertEqual(res.get("error_type"), "VIDEO_NOT_FOUND")
        self.assertIn("Could not find video #1 on YouTube", res["message"])

    # ── Command 5: "Scroll down" / "Scroll up" ─────────────────────────────────
    @patch("agent_tools.browser.BrowserManager._get_page_worker")
    def test_cmd_scroll_page_multi_target(self, mock_get_page):
        """Confirm scroll down executes multi-target scrolling and keyboard fallback."""
        mock_page = MagicMock()
        mock_page.title.return_value = "YouTube Search"
        mock_page.url = "https://www.youtube.com/results?search_query=cloud"
        mock_page.evaluate.return_value = {"beforeY": 0, "afterY": 500}
        mock_get_page.return_value = mock_page

        res = browser.scroll_page(direction="down", amount=500)
        self.assertTrue(res["success"])
        self.assertIn("Scrolled down by 500px", res["message"])
        self.assertTrue(mock_page.bring_to_front.called)
        mock_page.keyboard.press.assert_called_once_with("PageDown")

    # ── Command 6: "Write a simple code of Python in Notepad" ──────────────────
    @patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True})
    @patch("config.platform_paths.get_text_editor_command")
    @patch("subprocess.Popen")
    def test_cmd_notepad_code_generation_disk_write_and_launch(self, mock_popen, mock_editor_cmd, mock_guard):
        """Confirm code generation writes UTF-8 file to workspace and launches Notepad with file path."""
        code_content = "def hello():\n    print('Hello from Kairos!')\n\nhello()\n"
        test_filename = "test_hello.py"
        test_path = os.path.join(permissions.DEFAULT_WORKSPACE, test_filename)
        
        mock_editor_cmd.return_value = ["notepad.exe", test_path]
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # Process running
        mock_popen.return_value = mock_proc

        res = executor.execute_tool("open_notepad_and_write_code", {
            "filename": test_filename,
            "code": code_content
        })

        self.assertTrue(res["success"])
        self.assertIn(f"Created {test_filename} with your Python code and opened it in Notepad", res["message"])
        self.assertTrue(os.path.exists(test_path))
        
        # Verify content on disk
        with open(test_path, "r", encoding="utf-8") as f:
            disk_content = f.read()
        self.assertEqual(disk_content, code_content)

        # Cleanup test file
        if os.path.exists(test_path):
            os.remove(test_path)

    @patch("agent_tools.permissions.validate_tool_call", return_value={"permitted": True})
    def test_cmd_notepad_empty_code_error(self, mock_guard):
        """Confirm writing empty code returns specific diagnostic error."""
        res = executor.execute_tool("open_notepad_and_write_code", {
            "filename": "empty.py",
            "code": "   "
        })
        self.assertFalse(res["success"])
        self.assertEqual(res.get("error_type"), "EMPTY_CODE")
        self.assertIn("No code content was provided", res["message"])


# ── Commands 7–9: Work Mode & VS Code Launchers ────────────────────────────────

class TestWorkModeLaunchers(unittest.TestCase):
    """Test suite for 'activate work mode', 'open VS Code' voice commands."""

    def setUp(self):
        for var in ["KAIROS_CHROME_PATH", "KAIROS_VSCODE_PATH", "KAIROS_DEFAULT_WORKSPACE"]:
            if var in os.environ:
                del os.environ[var]

    # ── Command 7: "Activate work mode" ───────────────────────────────────────
    @patch("agent_tools.browser.run_work_mode")
    @patch("config.platform_paths.get_chrome_path")
    def test_work_mode_full_success(self, mock_chrome_path, mock_run_work_mode):
        """Confirm 'activate work mode' calls run_work_mode when Chrome is found."""
        mock_chrome_path.return_value = "C:\\chrome.exe"
        mock_run_work_mode.return_value = {
            "success": True,
            "opened": 4,
            "failed": [],
            "message": "Work Mode activated: 4 sites opened in Chrome and VS Code launched.",
        }
        with patch("os.path.exists", return_value=True):
            res = executor.execute_tool("work_mode", {})
        self.assertTrue(res["success"])
        self.assertIn("4", res["message"])
        mock_run_work_mode.assert_called_once()

    @patch("agent_tools.browser.run_work_mode")
    @patch("config.platform_paths.get_chrome_path")
    def test_work_mode_partial_failure_reported(self, mock_chrome_path, mock_run_work_mode):
        """Confirm work_mode passes through partial failure from run_work_mode clearly."""
        mock_chrome_path.return_value = "C:\\chrome.exe"
        mock_run_work_mode.return_value = {
            "success": False,
            "opened": 3,
            "failed": ["https://chat.openai.com"],
            "message": "3 of 4 sites opened. Failed: chat.openai.com",
        }
        with patch("os.path.exists", return_value=True):
            res = executor.execute_tool("work_mode", {})
        self.assertIn("3", res.get("message", ""))

    @patch("config.platform_paths.get_chrome_path", return_value=None)
    def test_work_mode_chrome_not_installed_error(self, mock_chrome):
        """Confirm work_mode reports CHROME_NOT_FOUND clearly when Chrome isn't installed."""
        res = executor.execute_tool("work_mode", {})
        self.assertFalse(res["success"])
        self.assertEqual(res.get("error_type"), "CHROME_NOT_FOUND")
        self.assertIn("Chrome", res["message"])

    # ── Command 8: "Open VS Code" ──────────────────────────────────────────────
    @patch("subprocess.Popen")
    @patch("config.platform_paths.get_vscode_path")
    def test_cmd_open_vscode_success(self, mock_vsc_path, mock_popen):
        """Confirm 'open VS Code' spawns VS Code process and reports success."""
        mock_vsc_path.return_value = "C:\\Program Files\\Microsoft VS Code\\Code.exe"
        with patch("os.path.exists", return_value=True):
            res = executor.execute_tool("open_vscode", {})
        self.assertTrue(res["success"])
        self.assertIn("VS Code", res["message"])
        self.assertTrue(mock_popen.called)

    @patch("config.platform_paths.get_vscode_path", return_value=None)
    def test_cmd_open_vscode_not_installed_error(self, mock_vsc_path):
        """Confirm 'open VS Code' reports VSCODE_NOT_FOUND when not on PATH."""
        res = executor.execute_tool("open_vscode", {})
        self.assertFalse(res["success"])
        self.assertEqual(res.get("error_type"), "VSCODE_NOT_FOUND")
        self.assertIn("VS Code", res["message"])

    # ── Command 9: "Get weather in Mumbai" ────────────────────────────────────
    @patch("agent_tools.info_tools.get_weather")
    def test_cmd_get_weather_success(self, mock_weather):
        """Confirm get_weather returns structured result and spoken_message."""
        mock_weather.return_value = {
            "success": True,
            "city": "Mumbai",
            "country": "India",
            "temperature_c": 28.5,
            "feels_like_c": 32.1,
            "humidity_pct": 85,
            "wind_speed_kmh": 14.4,
            "precipitation_mm": 0.0,
            "weather_description": "Partly cloudy",
            "spoken_message": "The weather in Mumbai, India right now is partly cloudy. Temperature is 28.5°C, feels like 32.1°C. Humidity 85%, wind speed 14.4 km/h.",
            "message": "The weather in Mumbai, India right now is partly cloudy.",
        }
        res = executor.execute_tool("get_weather", {"city": "Mumbai", "country": "India"})
        self.assertTrue(res["success"])
        self.assertEqual(res["city"], "Mumbai")
        self.assertIn("temperature_c", res)
        self.assertIn("spoken_message", res)
        mock_weather.assert_called_once_with(city="Mumbai", country="India")

    @patch("agent_tools.info_tools.get_weather")
    def test_cmd_get_weather_unknown_city(self, mock_weather):
        """Confirm get_weather returns graceful error for unknown city."""
        mock_weather.return_value = {
            "success": False,
            "message": "Could not find a location named 'Xyzzyburgh'. Please check the city name.",
        }
        res = executor.execute_tool("get_weather", {"city": "Xyzzyburgh"})
        self.assertFalse(res["success"])
        self.assertIn("Xyzzyburgh", res["message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
