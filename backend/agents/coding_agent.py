"""
coding_agent.py — Specialized sub-agent for code generation and sandbox execution.
"""

from agents.base_agent import BaseSubAgent


class CodingAgent(BaseSubAgent):
    name = "coding_agent"
    description = "Specialized sub-agent for software development, code generation, and sandbox execution."
    tool_names = [
        "open_vscode",
        "open_notepad_and_write_code",
        "open_vscode_and_write_code",
        "write_and_run_sandbox_code",
    ]
    system_prompt_addon = """
## CODING AGENT MODE:
You are Kairos's Coding Specialist.
- Your sole focus is producing high-quality, efficient, well-structured code.
- Always output clean code with standard formatting and clear comments.
- Choose the best destination tool:
  * `open_vscode_and_write_code`: DEFAULT choice for any code generation, writing scripts, creating programs, or code files.
  * `write_and_run_sandbox_code`: for interactive snippet execution or sandbox testing.
  * `open_notepad_and_write_code`: ONLY when the user explicitly asks to write in Notepad or take notes ("note karo", "notepad me likho", "write in notepad").
- If the user's coding request is ambiguous, provide the solution and explain key design choices cleanly.
"""
