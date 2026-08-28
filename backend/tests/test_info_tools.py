"""
test_info_tools.py — Integration and Unit Tests for Live Information, News & Web Search Utility Layer.
"""

import sys
import os
import time
import unittest
from unittest.mock import patch, MagicMock

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_tools import info_tools
from agent_tools import executor
from agent_tools.permissions import PERMITTED_TOOLS
from agent_tools.registry import TOOLS_SCHEMA, TOOL_AGENT_MAP


class TestInfoTools(unittest.TestCase):

    def setUp(self):
        # Clear in-memory caches before each test
        info_tools._NEWS_CACHE.clear()
        info_tools._SEARCH_CACHE.clear()
        for var in ["KAIROS_SEARCH_API_KEY", "KAIROS_TIMEZONE", "TAVILY_API_KEY"]:
            if var in os.environ:
                del os.environ[var]

    # ── 1. Date & Time Tests ──────────────────────────────────────────────────
    def test_get_current_datetime_default(self):
        """Test default system date and time detection."""
        res = info_tools.get_current_datetime()
        self.assertTrue(res["success"])
        self.assertIn("date", res)
        self.assertIn("day", res)
        self.assertIn("time", res)
        self.assertIn("timezone", res)
        self.assertIn("Today is", res["spoken_message"])

    def test_get_current_datetime_timezone_override(self):
        """Test explicit timezone override (e.g. UTC, Asia/Kolkata)."""
        res_kolkata = info_tools.get_current_datetime(timezone_override="Asia/Kolkata")
        self.assertTrue(res_kolkata["success"])
        self.assertIn("IST", res_kolkata["timezone"])

        res_utc = info_tools.get_current_datetime(timezone_override="UTC")
        self.assertTrue(res_utc["success"])
        self.assertIn("UTC", res_utc["timezone"])

    def test_get_current_datetime_env_var_override(self):
        """Test KAIROS_TIMEZONE environment variable override."""
        os.environ["KAIROS_TIMEZONE"] = "America/New_York"
        res = info_tools.get_current_datetime()
        self.assertTrue(res["success"])
        self.assertIn(res["timezone"], ["EDT", "EST", "America/New_York"])

    # ── 2. Live News Tests ────────────────────────────────────────────────────
    @patch("agent_tools.info_tools._fetch_google_news_rss")
    def test_get_news_hyperlocal_indian_city(self, mock_rss):
        """Test location-based news query (e.g. Muzaffarnagar news)."""
        mock_rss.return_value = [
            {"title": "Muzaffarnagar development projects inaugurated", "link": "https://example.com/1", "source": "Times of India", "pub_date": "2026-08-27"},
            {"title": "Farmers meeting concludes in Muzaffarnagar", "link": "https://example.com/2", "source": "Dainik Jagran", "pub_date": "2026-08-27"},
            {"title": "New solar power plant approved in UP", "link": "https://example.com/3", "source": "Amar Ujala", "pub_date": "2026-08-27"},
        ]

        res = executor.execute_tool("get_news", {"topic_or_location": "Muzaffarnagar"})
        self.assertTrue(res["success"])
        self.assertEqual(res["total_results"], 3)
        self.assertIn("Muzaffarnagar", res["spoken_message"])
        self.assertIn("Times of India", res["spoken_message"])
        self.assertIn("[Read more](https://example.com/1)", res["chat_markdown"])
        mock_rss.assert_called_once_with("Muzaffarnagar", max_results=5)

    @patch("agent_tools.info_tools._fetch_google_news_rss")
    def test_get_news_ttl_caching(self, mock_rss):
        """Test that duplicate news queries within TTL are served from cache without network calls."""
        mock_rss.return_value = [
            {"title": "Tech innovation summit opens", "link": "https://example.com/tech", "source": "TechCrunch", "pub_date": "2026-08-27"}
        ]

        # 1st call: hits network
        res1 = info_tools.get_news("tech news")
        self.assertTrue(res1["success"])
        self.assertEqual(mock_rss.call_count, 1)

        # 2nd call: served from memory cache
        res2 = info_tools.get_news("tech news")
        self.assertTrue(res2["success"])
        self.assertEqual(mock_rss.call_count, 1)  # No extra call!

    @patch("agent_tools.info_tools._fetch_google_news_rss", side_effect=Exception("Connection refused"))
    def test_get_news_network_failure_honest_reporting(self, mock_rss):
        """Test that news fetch failure reports honest refusal rather than hallucinating."""
        res = executor.execute_tool("get_news", {"topic_or_location": "world news"})
        self.assertFalse(res["success"])
        self.assertEqual(res.get("error_type"), "NEWS_FETCH_FAILED")
        self.assertIn("couldn't fetch live news", res["message"])

    # ── 3. General Question & Live Web Search Tests ────────────────────────────
    @patch("agent_tools.info_tools._fetch_duckduckgo_search")
    def test_answer_general_question_success(self, mock_search):
        """Test web-search backed general question answering."""
        mock_search.return_value = [
            {"title": "Super Bowl 2026", "snippet": "The Kansas City Chiefs won the championship in a thrilling match.", "url": "https://sports.example.com"},
            {"title": "Final Highlights", "snippet": "Full recap of the victory and key plays.", "url": "https://espn.example.com"}
        ]

        res = executor.execute_tool("answer_general_question", {"query": "who won super bowl 2026"})
        self.assertTrue(res["success"])
        self.assertIn("Kansas City Chiefs", res["answer"])
        self.assertIn("https://sports.example.com", res["chat_markdown"])

    @patch("agent_tools.info_tools._fetch_duckduckgo_search")
    def test_answer_general_question_ttl_caching(self, mock_search):
        """Test web search caching."""
        mock_search.return_value = [
            {"title": "Capital of France", "snippet": "Paris is the capital and most populous city of France.", "url": "https://wiki.example.com/Paris"}
        ]

        res1 = info_tools.answer_general_question("capital of France")
        self.assertTrue(res1["success"])
        self.assertEqual(mock_search.call_count, 1)

        res2 = info_tools.answer_general_question("capital of France")
        self.assertTrue(res2["success"])
        self.assertEqual(mock_search.call_count, 1)

    @patch("agent_tools.info_tools._fetch_google_news_rss", side_effect=Exception("Offline"))
    @patch("agent_tools.info_tools._fetch_duckduckgo_search", side_effect=Exception("Timeout"))
    def test_answer_general_question_failure_honest_reporting(self, mock_search, mock_news):
        """Test that search failure reports an honest refusal."""
        res = executor.execute_tool("answer_general_question", {"query": "unreachable query"})
        self.assertFalse(res["success"])
        self.assertEqual(res.get("error_type"), "SEARCH_FAILED")
        self.assertIn("couldn't find live information", res["message"])

    # ── 4. Permissions & Registry Schema Tests ────────────────────────────────
    def test_info_tools_in_permissions_and_registry(self):
        """Verify all 3 tools are registered as permitted read-only tools and mapped to info_agent."""
        tools = ["get_current_datetime", "get_news", "answer_general_question"]
        for t in tools:
            self.assertIn(t, PERMITTED_TOOLS)
            self.assertEqual(TOOL_AGENT_MAP.get(t), "info_agent")
            schema_names = [s["function"]["name"] for s in TOOLS_SCHEMA]
            self.assertIn(t, schema_names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
