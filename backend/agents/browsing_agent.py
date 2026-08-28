"""
browsing_agent.py — Specialized sub-agent for web navigation and YouTube automation.
"""

from agents.base_agent import BaseSubAgent


class BrowsingAgent(BaseSubAgent):
    name = "browsing_agent"
    description = "Specialized sub-agent for web searching, CDP browser navigation, and YouTube playback."
    tool_names = [
        "navigate_to",
        "find_and_click",
        "type_into",
        "scroll_page",
        "extract_page_text",
        "go_back",
        "open_new_tab",
        "switch_tab",
        "open_youtube_in_brave",
        "youtube_search",
        "youtube_play_video",
        "youtube_control",
        "open_brave",
        "work_mode",
    ]
    system_prompt_addon = """
## BROWSING AGENT MODE:
You are Kairos's Web & Browser Automation Specialist.
- Focus on precise web navigation, accurate element targeting, and fast page reading.
- Break down multi-step web tasks logically (e.g. navigate -> type -> click).
- Use `extract_page_text` to inspect web pages when relevant information needs to be read or summarized.
- For YouTube requests, prefer direct shortcuts (`youtube_search`, `youtube_play_video`, `youtube_control`).
"""
