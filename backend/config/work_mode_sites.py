"""
work_mode_sites.py — Configurable site list and workspace configuration for Work Mode.

Allows customization of developer websites and default VS Code workspace
without modifying core execution logic.
"""

import os
import json
from typing import List, Dict, Any

# Default Developer Sites to open in Google Chrome for Work Mode
DEFAULT_WORK_MODE_SITES: List[Dict[str, str]] = [
    {
        "name": "GitHub",
        "url": "https://github.com",
        "expected_keyword": "github"
    },
    {
        "name": "LeetCode",
        "url": "https://leetcode.com",
        "expected_keyword": "leetcode"
    },
    {
        "name": "Gmail",
        "url": "https://mail.google.com",
        "expected_keyword": "mail"
    },
    {
        "name": "ChatGPT",
        "url": "https://chat.openai.com",
        "expected_keyword": "chat"
    }
]


def get_work_mode_sites() -> List[Dict[str, str]]:
    """
    Returns the list of work mode websites.
    Can be overridden via KAIROS_WORK_MODE_SITES environment variable (JSON string).
    """
    env_override = os.environ.get("KAIROS_WORK_MODE_SITES")
    if env_override:
        try:
            custom_sites = json.loads(env_override)
            if isinstance(custom_sites, list) and custom_sites:
                return custom_sites
        except Exception as e:
            print(f"[WorkModeConfig] Failed to parse KAIROS_WORK_MODE_SITES JSON: {e}. Using defaults.")

    return [dict(site) for site in DEFAULT_WORK_MODE_SITES]


def get_default_workspace() -> str:
    """
    Returns the default workspace folder path for VS Code in Work Mode.
    Priority:
      1. KAIROS_DEFAULT_WORKSPACE environment variable
      2. ~/KairosWorkspace
    """
    env_override = os.environ.get("KAIROS_DEFAULT_WORKSPACE")
    if env_override and env_override.strip():
        return os.path.abspath(os.path.expanduser(env_override.strip().strip('"\'')))

    return os.path.abspath(os.path.expanduser(os.path.join("~", "KairosWorkspace")))
