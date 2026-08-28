"""
memory_agent.py — Specialized sub-agent for ChromaDB long-term memory and document retrieval.
"""

from agents.base_agent import BaseSubAgent


class MemoryAgent(BaseSubAgent):
    name = "memory_agent"
    description = "Specialized sub-agent for querying long-term user facts, ingested documents, and RAG memory."
    tool_names = []  # Uses memory_store RAG directly, no action tools required
    system_prompt_addon = """
## MEMORY & RESEARCH AGENT MODE:
You are Kairos's Long-Term Memory & Research Specialist.
- Retrieve and synthesize personal context, user facts, and ingested documents from long-term memory.
- Answer questions accurately using retrieved facts and document chunks.
- If information is missing from long-term memory, state so clearly and concisely.
"""
