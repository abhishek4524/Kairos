"""
test_developer_superpowers.py — Unit tests for Phase E (Developer Superpowers: Dev Tools & Dev Agent).
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from agent_tools import dev_tools
from agents.dev_agent import DevAgent
from agents import orchestrator


# ── Test 1: Project-Aware Context ──────────────────────────────────────────────

def test_project_context_stack_inference():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock Node/JS repo
        with open(os.path.join(tmpdir, "package.json"), "w") as f:
            f.write('{"name": "test-app"}')

        ctx = dev_tools.get_project_context(repo_root=tmpdir, force_refresh=True)
        assert "Node/JavaScript" in ctx["tech_stack"]
        assert ctx["repo_root"] == tmpdir
        assert "current_branch" in ctx
        assert "recent_commits" in ctx


# ── Test 2: Codebase RAG Hard Exclusions ──────────────────────────────────────

def test_codebase_rag_hard_exclusion_filters():
    # Secret files and dependency directories MUST be excluded
    assert dev_tools.is_allowed_codebase_file("/app/.env") is False
    assert dev_tools.is_allowed_codebase_file("/app/.env.production") is False
    assert dev_tools.is_allowed_codebase_file("/app/certs/server.pem") is False
    assert dev_tools.is_allowed_codebase_file("/app/keys/id_rsa.key") is False
    assert dev_tools.is_allowed_codebase_file("/app/node_modules/express/index.js") is False
    assert dev_tools.is_allowed_codebase_file("/app/.venv/lib/site.py") is False
    assert dev_tools.is_allowed_codebase_file("/app/.git/config") is False

    # Allowed codebase files
    assert dev_tools.is_allowed_codebase_file("/app/src/main.py") is True
    assert dev_tools.is_allowed_codebase_file("/app/frontend/App.jsx") is True
    assert dev_tools.is_allowed_codebase_file("/app/README.md") is True
    assert dev_tools.is_allowed_codebase_file("/app/package.json") is True


# ── Test 3: Terminal Copilot ──────────────────────────────────────────────────

def test_terminal_copilot_proposal():
    prop1 = dev_tools.propose_terminal_command("show me all files changed in the last commit")
    assert "git show" in prop1["command"] or "git diff" in prop1["command"]
    assert len(prop1["explanation"]) > 0
    assert prop1["requires_confirmation"] is True

    prop2 = dev_tools.propose_terminal_command("list all branches")
    assert "branch" in prop2["command"]


# ── Test 4: Git Assistant ──────────────────────────────────────────────────────

def test_git_assistant_commit_and_pr_generation():
    msg1 = dev_tools.generate_commit_message("Fix authentication bug in login endpoint")
    assert msg1.startswith("fix:")

    msg2 = dev_tools.generate_commit_message("Add comprehensive unit test suite")
    assert msg2.startswith("test:")

    pr = dev_tools.draft_pr_description(branch_name="feature/offline_intelligence", changes_summary="Added Ollama and Piper")
    assert "Offline intelligence" in pr["title"]
    assert "Added Ollama and Piper" in pr["body"]


# ── Test 5: Error Explainer ───────────────────────────────────────────────────

def test_error_explainer_stack_trace_parser():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("# line 1\n# line 2\n# line 3\nraise ValueError('test error')\n# line 5\n")
        fname = f.name

    try:
        sample_trace = f'Traceback (most recent call last):\n  File "{fname}", line 4, in <module>\n    raise ValueError("test error")\nValueError: test error'
        res = dev_tools.explain_error(sample_trace)
        assert res["located_file"] == fname
        assert res["line_number"] == 4
        assert "ValueError" in res["code_snippet"] or len(res["code_snippet"]) > 0
    finally:
        if os.path.exists(fname):
            os.remove(fname)


# ── Test 6: Hackathon & Focus Modes ───────────────────────────────────────────

def test_hackathon_and_focus_modes():
    with tempfile.TemporaryDirectory() as tmpdir:
        h_res = dev_tools.activate_hackathon_mode(deadline_hours=12.0, repo_root=tmpdir)
        assert h_res["success"] is True
        assert os.path.exists(os.path.join(tmpdir, "README_HACKATHON.md"))

    f_res = dev_tools.activate_focus_mode(duration_minutes=30)
    assert f_res["success"] is True
    assert f_res["focus_active"] is True
    assert "twitter.com" in f_res["blocked_domains"]


# ── Test 7: DevAgent Orchestration ───────────────────────────────────────────

def test_dev_agent_registered_in_orchestrator():
    agent, category = orchestrator.get_agent_for_category("dev", confidence=0.95)
    assert isinstance(agent, DevAgent)
    assert category == "dev"
    assert "get_project_context" in agent.tool_names
    assert "explain_git_diff" in agent.tool_names
