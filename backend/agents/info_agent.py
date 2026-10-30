"""
info_agent.py — Specialized sub-agent for live real-time world intelligence, news, and utilities.
"""

from agents.base_agent import BaseSubAgent


class InfoAgent(BaseSubAgent):
    name = "info_agent"
    description = "Specialized sub-agent for live world intelligence, date/time queries, hyperlocal & global news, and web search."
    tool_names = [
        "get_current_datetime",
        "get_weather",
        "get_news",
        "answer_general_question",
        "query_spreadsheet",
    ]
    system_prompt_addon = """
## LIVE INFORMATION & UTILITY SPECIALIST:
You are Kairos's Real-Time Knowledge & Utility Specialist.
- For date, day of week, or time questions (e.g. "aaj date kya hai", "what time is it", "what day is today"):
  Use `get_current_datetime`.
- For live news, current headlines, local/state news, or tech updates (e.g. "aaj ki Muzaffarnagar news bata", "Uttar Pradesh news today", "what's new in tech today", "world news"):
  Use `get_news` with the topic or location.
- For general knowledge questions, live events, sports scores, weather, facts, or questions requiring current information (e.g. "who won the match yesterday", "what is the capital of Australia", "weather in Delhi"):
  Use `answer_general_question`.
- ALWAYS provide a crisp, concise, voice-friendly spoken summary (2-4 sentences max for voice TTS).
- NEVER guess or hallucinate current/live events from training memory when real-time tools are available.
"""
