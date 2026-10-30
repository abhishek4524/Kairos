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
        "read_page",
        "go_back",
        "open_new_tab",
        "switch_tab",
        "open_youtube_in_brave",
        "youtube_search",
        "youtube_play_video",
        "youtube_control",
        "youtube_like_video",
        "youtube_subscribe",
        "open_github",
        "open_instagram",
        "instagram_action",
        "open_brave",
        "work_mode",
    ]
    system_prompt_addon = """
## BROWSING AGENT MODE:
You are Kairos's Web & Browser Automation Specialist.
- ALWAYS output an `[ACTION:{"tool":"...","params":{...}}]` tag whenever any web navigation, search, or browsing task is requested.
- When Abhishek asks to open YouTube ("open youtube", "youtube chalao", "open youtube.com"):
  → ALWAYS output `[ACTION:{"tool":"navigate_to","params":{"url_or_search_query":"https://www.youtube.com"},"summary":"Open YouTube"}]` followed by a brief sentence.
- When Abhishek asks to play or search something on YouTube ("play lofi on youtube", "search lofi"):
  → ALWAYS output `[ACTION:{"tool":"youtube_search","params":{"query":"<search query>"},"summary":"Search YouTube"}]` or `navigate_to`.
- When Abhishek asks to open ANY website or search on Google / Web:
  → ALWAYS output `[ACTION:{"tool":"navigate_to","params":{"url_or_search_query":"<url or query>"},"summary":"Navigate to website"}]`.
- NEVER reply with only a text promise without the `[ACTION:{...}]` tag!
"""
