"""
test_browser_suite.py — Verification suite for Kairos Generic Browser Automation.
"""

import sys
import os
import unittest

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_tools.registry import TOOLS_SCHEMA, format_system_tools_prompt
from agent_tools.executor import execute_tool
from agent_tools import browser


class TestBrowserAutomation(unittest.TestCase):

    def test_schemas(self):
        tool_names = [t["function"]["name"] for t in TOOLS_SCHEMA]
        expected_tools = [
            "navigate_to", "find_and_click", "type_into", "scroll_page",
            "extract_page_text", "go_back", "open_new_tab", "switch_tab",
            "open_youtube_in_brave", "youtube_search", "youtube_play_video",
            "youtube_control", "open_app", "close_app", "cursor_control",
            "open_vscode_and_write_code", "open_notepad_and_write_code",
            "write_and_run_sandbox_code", "work_mode"
        ]
        for t in expected_tools:
            self.assertIn(t, tool_names, f"Missing tool in schema: {t}")

    def test_system_prompt_content(self):
        prompt = format_system_tools_prompt()
        self.assertIn("navigate_to", prompt)
        self.assertIn("find_and_click", prompt)
        self.assertIn("type_into", prompt)
        self.assertIn("extract_page_text", prompt)
        self.assertIn("scroll_page", prompt)
        self.assertIn("MULTI-STEP WEB TASK EXAMPLES", prompt)

    def test_ordinal_extraction(self):
        cases = [
            ("the 2nd search result", 2, "the search result"),
            ("first button", 1, "button"),
            ("3rd link", 3, "link"),
            ("4th article", 4, "article"),
            ("submit button", None, "submit button"),
            ("10th row", 10, "row"),
        ]
        for query, expected_idx, expected_clean in cases:
            idx, clean = browser._extract_ordinal(query)
            self.assertEqual(idx, expected_idx, f"Ordinal failed for {query}")
            self.assertEqual(clean, expected_clean, f"Clean failed for {query}")

    def test_unknown_tool_handling(self):
        res = execute_tool("non_existent_tool", {})
        self.assertFalse(res["success"])
        self.assertTrue("not in the Kairos permitted tools allowlist" in res["message"] or "Unknown tool" in res["message"])

    def test_element_confirmation_builder(self):
        # Verify helper doesn't crash on dummy/null
        class MockLocator:
            def evaluate(self, expr):
                if "tagName" in expr:
                    return "button"
                if "innerText" in expr:
                    return "Submit Order"
                if "aria-label" in expr:
                    return "Submit Order Button"
                if "id" in expr:
                    return "btn-submit"
                return ""
            def bounding_box(self):
                return {"x": 100, "y": 200, "width": 80, "height": 30}

        conf = browser._extract_element_confirmation(MockLocator())
        self.assertEqual(conf["tag"], "button")
        self.assertEqual(conf["text"], "Submit Order")
        self.assertEqual(conf["aria_label"], "Submit Order Button")
        self.assertEqual(conf["id"], "btn-submit")
        self.assertEqual(conf["box"]["x"], 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
