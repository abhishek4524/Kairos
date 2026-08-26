"""
registry.py — Extensible Agentic Tools & Skills Registry for Kairos.

Defines schemas, execution metadata, and helper parsing for desktop OS & browser automation tools.
"""

import json
import re

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open or focus a desktop application on the user's computer (e.g. Brave, Chrome, VS Code, Spotify, Notepad, Calculator, Discord, Terminal).",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name or executable of the application (e.g. 'brave', 'chrome', 'notepad', 'calc', 'code', 'spotify', 'cmd')"
                    }
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_app",
            "description": "Close or terminate a running desktop application on the user's computer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the application to close (e.g. 'calculator', 'notepad', 'chrome', 'brave', 'calc', 'code')"
                    }
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_youtube_in_brave",
            "description": "Open YouTube in Brave browser, or navigate directly to YouTube home/search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Optional search term or song to search immediately"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "youtube_search",
            "description": "Search inside YouTube for a query or video title in Brave browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query or video topic to search on YouTube"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "youtube_play_video",
            "description": "Play the N-th video from the current YouTube search results or homepage (e.g. 1st, 2nd, 3rd, 4th video).",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "The 1-based index of the video to play (1 for 1st, 2 for 2nd, 3 for 3rd, etc.)"
                    }
                },
                "required": ["index"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scroll_page",
            "description": "Scroll the active web browser or window up or down.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["down", "up"],
                        "description": "Scroll direction ('down' or 'up')"
                    },
                    "amount": {
                        "type": "integer",
                        "description": "Amount to scroll in pixels/ticks (default: 500)"
                    }
                },
                "required": ["direction"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "youtube_control",
            "description": "Control YouTube video playback: play, pause, mute, unmute, fullscreen, volume up/down, seek forward/back, next video.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["play_pause", "mute", "fullscreen", "volume_up", "volume_down", "seek_forward", "seek_backward", "next_video", "restart"],
                        "description": "Playback action to perform"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cursor_control",
            "description": "Autonomous mouse cursor and keyboard actions on desktop (click, double-click, move, type, press key).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["click", "double_click", "right_click", "move", "type_text", "press_key"],
                        "description": "Cursor/keyboard action"
                    },
                    "x": { "type": "integer", "description": "Target X screen coordinate (optional)" },
                    "y": { "type": "integer", "description": "Target Y screen coordinate (optional)" },
                    "text": { "type": "string", "description": "Text to type (for type_text)" },
                    "key": { "type": "string", "description": "Key name to press (e.g. 'enter', 'space', 'esc')" }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_vscode_and_write_code",
            "description": "Create or write a code file with the given code content and immediately open it in VS Code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Filename with extension (e.g. 'solution.py', 'script.js')"
                    },
                    "code": {
                        "type": "string",
                        "description": "The complete source code to write into the file"
                    }
                },
                "required": ["filename", "code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_and_run_sandbox_code",
            "description": "Write code into Kairos's live Monaco code sandbox and execute it in an isolated subprocess.",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "enum": ["python", "javascript"],
                        "description": "Programming language ('python' or 'javascript')"
                    },
                    "code": {
                        "type": "string",
                        "description": "Source code to run in sandbox"
                    },
                    "auto_run": {
                        "type": "boolean",
                        "description": "Whether to execute automatically (default: true)"
                    },
                    "filename": {
                        "type": "string",
                        "description": "Suggested filename (e.g. 'two_sum.py')"
                    }
                },
                "required": ["language", "code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "work_mode",
            "description": "Activate Abhishek's full work setup: opens GitHub profile, LeetCode profile, Gmail, ChatGPT in Brave browser tabs, then opens VS Code.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

# Tools that require explicit user confirmation before executing
SENSITIVE_TOOLS = {
    "check_whatsapp_notifications": "Read WhatsApp messages/notifications",
    "delete_file": "Delete a file from the desktop",
    "send_email": "Send an email"
}

def is_sensitive(tool_name: str) -> bool:
    return tool_name in SENSITIVE_TOOLS

ACTION_TAG_REGEX = re.compile(r'\[ACTION:(\{.*?\})\]', re.DOTALL)

def format_system_tools_prompt() -> str:
    """Compact tools prompt — keeps token count low to prevent Groq context overflow."""
    return """
## DESKTOP AUTOMATION — AGENTIC TOOLS:
When the user asks to open apps, search YouTube, scroll, control media, or write code, OUTPUT an [ACTION:{...}] tag FIRST, then a single short English acknowledgment sentence.

FORMAT: [ACTION:{"tool":"<name>","params":{...},"summary":"..."}]

TOOL REFERENCE:
- open_app → {"app_name":"brave"} — open/focus any app (brave, chrome, code, spotify, calc, notepad, etc.)
- open_youtube_in_brave → {} — open YouTube in Brave browser
- youtube_search → {"query":"..."} — search on YouTube (use when user says "search X" or "X search karo")
- youtube_play_video → {"index":1} — play 1st/2nd/3rd video from results (1-based index)
- scroll_page → {"direction":"down","amount":500} — scroll browser up or down
- youtube_control → {"action":"play_pause"} — playback: play_pause, mute, fullscreen, volume_up, volume_down, seek_forward, seek_backward, next_video
- cursor_control → {"action":"click","x":500,"y":400} — mouse/keyboard: click, double_click, right_click, move, type_text, press_key
- open_notepad_and_write_code → {"filename":"script.py","code":"..."} — write code and open in Notepad (use when user says "write code in notepad" or "notepad me code likho")
- open_vscode_and_write_code → {"filename":"main.py","code":"..."} — write code and open in VS Code (use when user says "write code in vs code" or "vs code me code likho")
- write_and_run_sandbox_code → {"language":"python","code":"...","auto_run":true} — run in live Monaco sandbox
- work_mode → {} — open GitHub, LeetCode, Gmail, ChatGPT in Chrome + VS Code + Brave

EXAMPLES:
User: "open brave" → [ACTION:{"tool":"open_app","params":{"app_name":"brave"},"summary":"Open Brave"}] Opening Brave for you, sir!
User: "open youtube" → [ACTION:{"tool":"open_youtube_in_brave","params":{},"summary":"Open YouTube"}] Opening YouTube in Brave!
User: "search Networking" → [ACTION:{"tool":"youtube_search","params":{"query":"Networking"},"summary":"Search Networking on YouTube"}] Searching YouTube for Networking!
User: "play 1st video" → [ACTION:{"tool":"youtube_play_video","params":{"index":1},"summary":"Play 1st video"}] Playing the 1st video!
User: "scroll down" → [ACTION:{"tool":"scroll_page","params":{"direction":"down","amount":500},"summary":"Scroll down"}] Scrolling down!
User: "write normal python code in notepad" → [ACTION:{"tool":"open_notepad_and_write_code","params":{"filename":"hello.py","code":"print('Hello, Abhishek!')"},"summary":"Write Python in Notepad"}] Opening Notepad with your Python code!
User: "write a react component in vs code" → [ACTION:{"tool":"open_vscode_and_write_code","params":{"filename":"Counter.jsx","code":"import React from 'react';\\nexport default function Counter() { return <div>Count</div>; }"},"summary":"Write in VS Code"}] Opening VS Code with your React code!
"""
