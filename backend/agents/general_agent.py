"""
general_agent.py — Specialized sub-agent for conversational chitchat and ambiguous request clarification.
"""

from agents.base_agent import BaseSubAgent


class GeneralAgent(BaseSubAgent):
    name = "general_agent"
    description = "Fallback sub-agent for general conversation, chitchat, and clarifying ambiguous requests."
    tool_names = []  # No tools needed for general conversation
    system_prompt_addon = """
## GENERAL CONVERSATION MODE:
You are Kairos in friendly companion & personal assistant mode.
- Provide crisp, natural, engaging conversation.
- If the user's intent was ambiguous or underspecified, politely ask a clarifying question rather than making assumptions or executing incorrect tools.
"""
