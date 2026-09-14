"""
dev_agent.py — Developer Superpowers Specialist Sub-Agent for Kairos.
"""

from typing import List
from agents.base_agent import BaseSubAgent


class DevAgent(BaseSubAgent):
    name: str = "dev"
    description: str = "Developer companion for codebase exploration, git operations, terminal copilot, error explaining, and focus/hackathon sessions."

    tool_names: List[str] = [
        "get_project_context",
        "query_codebase",
        "propose_terminal_command",
        "explain_git_diff",
        "explain_error",
        "activate_hackathon_mode",
        "activate_focus_mode",
        "open_vscode",
        "open_vscode_and_write_code",
        "write_and_run_sandbox_code",
    ]

    system_prompt_addon: str = """
## DEVELOPER MODE & CODING COMPANION:
You have deep project-aware developer capabilities:
- Project Context: You understand the repository structure, branch, and commit history.
- Codebase Search: You can query codebase knowledge vectors.
- Terminal Copilot: You propose precise commands with 1-line explanations.
- Git Assistant: You can summarize diffs, generate Conventional Commit messages, and draft PRs.
- Error Explainer: You parse stack traces and locate code regions to propose fixes.
- Hackathon / Focus Mode: You can scaffold project templates and activate distraction-free Pomodoro timers.
"""
