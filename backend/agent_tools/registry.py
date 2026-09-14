"""
registry.py — Extensible Agentic Tools & Skills Registry for Kairos.

Defines schemas, execution metadata, and helper parsing for generic browser automation
(Playwright over CDP) and desktop OS automation.
"""

import json
import re

TOOLS_SCHEMA = [
    # ── Generic Browser Primitives (Playwright / CDP) ─────────────────────────
    {
        "type": "function",
        "function": {
            "name": "navigate_to",
            "description": "Navigate to any URL or search query in Google Chrome browser. If given a query or search terms, uses the search engine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url_or_search_query": {
                        "type": "string",
                        "description": "The destination URL (e.g. 'https://en.wikipedia.org', 'amazon.com', 'makemytrip.com') or search term (e.g. 'flights from Delhi to Mumbai')"
                    }
                },
                "required": ["url_or_search_query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_and_click",
            "description": "Find and click any element on the current web page described in plain natural language (e.g. 'search button', 'the second flight result', 'login link', 'add to cart', 'first video').",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Natural language description, accessible label, button text, link text, or ordinal target (e.g. 'second article', 'submit', 'Book Now')"
                    }
                },
                "required": ["description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_into",
            "description": "Type text into an input field, search box, or textarea identified by its description or placeholder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Description, placeholder, or label of the target input field (e.g. 'search box', 'destination input', 'email', 'password')"
                    },
                    "text": {
                        "type": "string",
                        "description": "The exact text or query to type into the field"
                    },
                    "press_enter": {
                        "type": "boolean",
                        "description": "Whether to press Enter after typing (default: false)"
                    }
                },
                "required": ["description", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scroll_page",
            "description": "Scroll the active web page up or down.",
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
                        "description": "Amount to scroll in pixels (default: 500)"
                    }
                },
                "required": ["direction"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_page_text",
            "description": "Extract and read the text content, page title, URL, and interactive elements of the active web page to summarize or answer questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum characters to extract (default: 3000)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "go_back",
            "description": "Navigate back to the previous page in browser history.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_new_tab",
            "description": "Open a new browser tab, optionally navigating directly to a URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Optional destination URL for the new tab"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "switch_tab",
            "description": "Switch active tab by 1-based index or matching title/URL substring.",
            "parameters": {
                "type": "object",
                "properties": {
                    "index_or_description": {
                        "description": "Tab index (e.g. 1, 2) or title/URL keyword (e.g. 'github', 'youtube')"
                    }
                },
                "required": ["index_or_description"]
            }
        }
    },

    # ── Backward-Compatibility YouTube Shortcuts ──────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "open_youtube_in_brave",
            "description": "Convenience shortcut: Open YouTube home or search in Brave browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": { "type": "string", "description": "Optional search query" }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "youtube_search",
            "description": "Convenience shortcut: Search inside YouTube in Brave browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": { "type": "string", "description": "Search query" }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "youtube_play_video",
            "description": "Convenience shortcut: Play Nth video from YouTube search results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": { "type": "integer", "description": "1-based video index" }
                },
                "required": ["index"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "youtube_control",
            "description": "Convenience shortcut: Control YouTube playback (play_pause, mute, fullscreen, volume_up, volume_down, seek_forward, seek_backward, next_video).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["play_pause", "mute", "fullscreen", "volume_up", "volume_down", "seek_forward", "seek_backward", "next_video", "restart"],
                        "description": "Playback action"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "youtube_like_video",
            "description": "Like the currently playing YouTube video.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "youtube_subscribe",
            "description": "Subscribe to the YouTube channel of the currently playing video.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_github",
            "description": "Open GitHub website or profile in browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": { "type": "string", "description": "Optional path or page (e.g. 'notifications', 'repositories', 'explore')" }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_instagram",
            "description": "Open Instagram in browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": { "type": "string", "description": "Optional path (e.g. 'direct', 'reels', 'explore', username)" }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "instagram_action",
            "description": "Perform actions on Instagram (like_post, search_user, view_reels, view_messages, scroll).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["like_post", "search_user", "view_reels", "view_messages", "scroll_down", "scroll_up"],
                        "description": "Action to perform on Instagram"
                    },
                    "target": { "type": "string", "description": "Optional target user or query" }
                },
                "required": ["action"]
            }
        }
    },

    # ── Desktop OS & Application Management ──────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "open_brave",
            "description": "Standalone launcher: Launch or focus Brave browser on desktop.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_vscode",
            "description": "Standalone launcher: Launch Visual Studio Code on desktop.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
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
                        "description": "Name of the application (e.g. 'brave', 'chrome', 'notepad', 'calc', 'code', 'spotify', 'cmd')"
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
            "name": "cursor_control",
            "description": "Autonomous mouse cursor and keyboard actions on desktop (click, double_click, move, type_text, press_key).",
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
            "name": "open_notepad_and_write_code",
            "description": "Write code into a file and immediately open it in Notepad.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": { "type": "string", "description": "Filename (e.g. 'notes.txt', 'script.py')" },
                    "code": { "type": "string", "description": "Text or code to write" }
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
            "description": "Activate Abhishek's full work setup: opens GitHub profile, LeetCode profile, Gmail, ChatGPT in browser tabs, then opens VS Code.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp_desktop_message",
            "description": "Send a message to a contact using the native WhatsApp Desktop standalone application.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {
                        "type": "string",
                        "description": "The exact name of the contact as saved in WhatsApp Desktop (e.g. 'Vansh Kumar', 'Mom'). Searching will be done on this text."
                    },
                    "message": {
                        "type": "string",
                        "description": "The text message body to send."
                    }
                },
                "required": ["recipient", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_whatsapp_chat",
            "description": "Open, search, or focus a specific contact's chat window in native WhatsApp Desktop (without sending a message). Use this whenever user says 'open chat of X', 'show chat of X', or 'search contact X on WhatsApp'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {
                        "type": "string",
                        "description": "Contact name to search and open chat for (e.g. 'Akhil Dondal', 'Vansh', 'Mom')"
                    }
                },
                "required": ["recipient"]
            }
        }
    },
    # ── Live Real-Time Knowledge, News & Utility Tools (Read-Only) ────────────
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": "Get current date, day of week, and time in the user's local timezone (or specified timezone).",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone_override": {
                        "type": "string",
                        "description": "Optional timezone identifier (e.g. 'Asia/Kolkata', 'America/New_York', 'UTC')."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current live weather for any city or location worldwide. Use this for ANY weather question: 'what's the weather in Mumbai', 'kaisa mausam hai Delhi mein', 'will it rain today in London', etc. Returns temperature, feels-like, humidity, wind speed, and a spoken description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name to get weather for (e.g. 'Mumbai', 'London', 'New York', 'Muzaffarnagar')"
                    },
                    "country": {
                        "type": "string",
                        "description": "Optional country name or ISO code to disambiguate cities with the same name (e.g. 'India', 'US', 'UK')"
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "Fetch and summarize live real-time news for a specific topic or location (e.g. 'Muzaffarnagar', 'Uttar Pradesh', 'tech news today', 'world news').",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic_or_location": {
                        "type": "string",
                        "description": "Topic or Indian city/state/country location (e.g. 'Muzaffarnagar', 'Uttar Pradesh', 'tech', 'business')"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "answer_general_question",
            "description": "Answer live world knowledge, current events, weather, quick facts, or general questions using real-time web search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query or general question (e.g. 'who won the match yesterday', 'weather in Delhi', 'latest SpaceX launch')"
                    }
                },
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_spreadsheet",
            "description": "Execute pandas numeric aggregations, sums, averages, column stats, or filtered row lookups on an ingested CSV or Excel spreadsheet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_name": {
                        "type": "string",
                        "description": "Optional filename of the ingested spreadsheet (e.g. 'sales.xlsx', 'data.csv')"
                    },
                    "query": {
                        "type": "string",
                        "description": "The numeric or analytical question (e.g. 'what is the sum of column Y', 'average price', 'total rows')"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_folder",
            "description": "Create a new folder or directory at the specified location (e.g. Desktop, Documents, Downloads, or custom folder path).",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_name": {
                        "type": "string",
                        "description": "Name or relative path of the folder to create (e.g. 'oncecene', 'projects/my_app', 'Desktop/photos')"
                    },
                    "parent_dir": {
                        "type": "string",
                        "description": "Optional parent directory location (e.g. 'desktop', 'documents', 'downloads')"
                    }
                },
                "required": ["folder_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file with optional text content on Desktop, Documents, or specified path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Name or path of the file to create (e.g. 'notes.txt', 'script.py', 'Desktop/todo.txt')"
                    },
                    "content": {
                        "type": "string",
                        "description": "Optional initial text content to write into the file"
                    },
                    "parent_dir": {
                        "type": "string",
                        "description": "Optional parent directory location (e.g. 'desktop', 'documents')"
                    }
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rename_file_or_folder",
            "description": "Rename or move an existing file or folder to a new name or path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_name": {
                        "type": "string",
                        "description": "Current name or path of the file or folder (e.g. 'oncecene', 'notes.txt')"
                    },
                    "new_name": {
                        "type": "string",
                        "description": "New name or path for the file or folder (e.g. 'new_project', 'updated_notes.txt')"
                    },
                    "parent_dir": {
                        "type": "string",
                        "description": "Optional parent directory location if relative (e.g. 'desktop')"
                    }
                },
                "required": ["old_name", "new_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory_contents",
            "description": "List files and subfolders inside a given folder (e.g. Desktop, Documents, Downloads).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path or keyword location to list (e.g. 'desktop', 'documents', 'C:/Users/...')"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "start_camera_gesture_control",
            "description": "Start camera hand gesture control. When active, opening right hand finger tips increases screen brightness, closing right hand finger tips decreases screen brightness, opening left hand finger tips increases volume, and closing left hand finger tips decreases volume.",
            "parameters": {
                "type": "object",
                "properties": {
                    "show_preview": {
                        "type": "boolean",
                        "description": "Optional flag to show live camera feedback preview window (default false)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stop_camera_gesture_control",
            "description": "Stop the camera hand gesture control system.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_camera_gesture_status",
            "description": "Check if camera hand gesture control is active and get current brightness, volume, mode ('system' or 'avatar'), and detected hand state.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_camera_gesture_mode",
            "description": "Switch the camera hand gesture control mode between system control ('system': Brightness/Volume) and 3D model control ('avatar': 3D rotation and zoom).",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "description": "Mode to switch to: 'system' for Brightness/Volume, or 'avatar' for 3D model rotation/zoom",
                        "enum": ["system", "avatar"]
                    }
                },
                "required": ["mode"]
            }
        }
    }
]

# Tools that require explicit user confirmation before executing
SENSITIVE_TOOLS = {
    "check_whatsapp_notifications": "Read WhatsApp messages/notifications",
    "delete_file": "Delete a file from the desktop",
    "send_email": "Send an email",
}

def is_sensitive(tool_name: str) -> bool:
    return tool_name in SENSITIVE_TOOLS

ACTION_TAG_REGEX = re.compile(r'\[ACTION:(\{.*?\})\]', re.DOTALL)

# ── Sub-agent tool ownership map ──────────────────────────────────────────────
# Maps each tool name → the sub-agent module responsible for it.
# Used by registry docs, benchmark, and sub-agent tool-subset filtering.
TOOL_AGENT_MAP: dict = {
    # browsing_agent
    "navigate_to":             "browsing_agent",
    "find_and_click":          "browsing_agent",
    "type_into":               "browsing_agent",
    "scroll_page":             "browsing_agent",
    "extract_page_text":       "browsing_agent",
    "read_page":               "browsing_agent",
    "go_back":                 "browsing_agent",
    "open_new_tab":            "browsing_agent",
    "switch_tab":              "browsing_agent",
    "open_youtube_in_brave":   "browsing_agent",
    "youtube_search":          "browsing_agent",
    "youtube_play_video":      "browsing_agent",
    "youtube_control":         "browsing_agent",
    "youtube_like_video":      "browsing_agent",
    "youtube_subscribe":       "browsing_agent",
    "open_github":              "browsing_agent",
    "open_instagram":           "browsing_agent",
    "instagram_action":         "browsing_agent",
    "open_brave":              "browsing_agent",
    "work_mode":               "browsing_agent",
    # coding_agent
    "open_vscode":                 "coding_agent",
    "open_notepad_and_write_code": "coding_agent",
    "open_vscode_and_write_code":  "coding_agent",
    "write_and_run_sandbox_code":  "coding_agent",
    # system_agent
    "open_app":                       "system_agent",
    "close_app":                      "system_agent",
    "cursor_control":                 "system_agent",
    "type_in_active_window":          "system_agent",
    "delete_file":                    "system_agent",
    "send_email":                     "system_agent",
    "send_whatsapp_message":          "system_agent",
    "send_whatsapp_desktop_message":  "system_agent",
    "open_whatsapp_chat":             "system_agent",
    "check_whatsapp_notifications":   "system_agent",
    "create_folder":                  "system_agent",
    "create_file":                    "system_agent",
    "rename_file_or_folder":          "system_agent",
    "list_directory_contents":        "system_agent",
    "start_camera_gesture_control":   "system_agent",
    "stop_camera_gesture_control":    "system_agent",
    "get_camera_gesture_status":     "system_agent",
    "set_camera_gesture_mode":       "system_agent",
    # info_agent (Live Knowledge & Utilities)
    "get_current_datetime":    "info_agent",
    "get_weather":             "info_agent",
    "get_news":                "info_agent",
    "answer_general_question": "info_agent",
    "query_spreadsheet":       "info_agent",
    # memory_agent — no action tools, uses memory_store directly
    # general_agent — no tools
}


def get_tool_schemas_for_agent(tool_names: list) -> list:
    """Return the TOOLS_SCHEMA entries whose function.name is in tool_names."""
    name_set = set(tool_names)
    return [t for t in TOOLS_SCHEMA if t["function"]["name"] in name_set]


def format_system_tools_prompt(tool_names: list = None) -> str:
    """
    Compact tools prompt injected into the LLM system message.

    Args:
        tool_names: Optional list of tool names to include. When provided, only
                    those tools appear in the prompt (sub-agent focused mode).
                    When None, all tools are included (legacy single-agent mode).
    """
    # Determine which tools are in scope
    active = set(tool_names) if tool_names else None

    def _include(name: str) -> bool:
        return active is None or name in active

    lines = [
        "## DESKTOP & WEB AUTOMATION TOOLS:",
        "When the user asks to browse websites, search the web, interact with page elements, open apps, control media, or write code, OUTPUT an `[ACTION:{...}]` tag FIRST, followed by a brief, natural English acknowledgment sentence.",
        "",
        "FORMAT: [ACTION:{\"tool\":\"<name>\",\"params\":{...},\"summary\":\"...\"}]",
    ]

    # Browser primitives
    browser_tools = [
        ("navigate_to",     "`navigate_to` → `{\"url_or_search_query\":\"https://example.com\"}`"),
        ("find_and_click",  "`find_and_click` → `{\"description\":\"Book Now\"}`"),
        ("type_into",       "`type_into` → `{\"description\":\"Search destination\",\"text\":\"Mumbai\",\"press_enter\":true}`"),
        ("scroll_page",     "`scroll_page` → `{\"direction\":\"down\",\"amount\":500}`"),
        ("extract_page_text", "`extract_page_text` → `{}` — read page content & interactive elements"),
        ("go_back",         "`go_back` → `{}` — browser back button"),
        ("open_new_tab",    "`open_new_tab` → `{\"url\":\"https://...\"}`"),
        ("switch_tab",      "`switch_tab` → `{\"index_or_description\":\"github\"}`"),
    ]
    browser_entries = [desc for name, desc in browser_tools if _include(name)]
    if browser_entries:
        lines += ["", "GENERIC BROWSER PRIMITIVES (WORKS ON ANY WEBSITE VIA CDP):"] + browser_entries

    # YouTube shortcuts
    yt_tools = [
        ("open_youtube_in_brave", "`open_youtube_in_brave` → `{\"query\":\"lofi\"}` — open YouTube"),
        ("youtube_search",        "`youtube_search` → `{\"query\":\"lofi music\"}` — search on YouTube"),
        ("youtube_play_video",    "`youtube_play_video` → `{\"index\":2}` — play Nth result"),
        ("youtube_control",       "`youtube_control` → `{\"action\":\"play_pause\"}` — playback control"),
    ]
    yt_entries = [desc for name, desc in yt_tools if _include(name)]
    if yt_entries:
        lines += ["", "YOUTUBE SHORTCUTS:"] + yt_entries

    # Desktop / OS tools
    os_tools = [
        ("open_app",     "`open_app` → `{\"app_name\":\"chrome\"}`"),
        ("open_brave",   "`open_brave` → `{}` — launch/focus Brave browser"),
        ("open_vscode",  "`open_vscode` → `{}` — launch Visual Studio Code"),
        ("close_app",    "`close_app` → `{\"app_name\":\"calc\"}`"),
        ("cursor_control", "`cursor_control` → `{\"action\":\"click\",\"x\":500,\"y\":400}`"),
        ("type_in_active_window", "`type_in_active_window` → `{\"text\":\"hello\"}`"),
        ("work_mode",    "`work_mode` → `{}` — open GitHub, LeetCode, Gmail, ChatGPT in Chrome & VS Code"),
    ]
    os_entries = [desc for name, desc in os_tools if _include(name)]
    if os_entries:
        lines += ["", "DESKTOP APPS & OS TOOLS:"] + os_entries

    # File & Folder Management tools
    file_tools = [
        ("create_folder",          "`create_folder` → `{\"folder_name\":\"oncecene\",\"parent_dir\":\"desktop\"}` — create folder on Desktop or path"),
        ("create_file",            "`create_file` → `{\"filename\":\"notes.txt\",\"content\":\"hello\",\"parent_dir\":\"desktop\"}` — create text file"),
        ("rename_file_or_folder",  "`rename_file_or_folder` → `{\"old_name\":\"oncecene\",\"new_name\":\"my_project\",\"parent_dir\":\"desktop\"}` — rename folder or file"),
        ("list_directory_contents", "`list_directory_contents` → `{\"path\":\"desktop\"}` — list files & folders"),
    ]
    file_entries = [desc for name, desc in file_tools if _include(name)]
    if file_entries:
        lines += ["", "FILE & FOLDER MANAGEMENT TOOLS:"] + file_entries

    # Info / live knowledge tools
    info_tools = [
        ("get_current_datetime", "`get_current_datetime` → `{}` — get current date, day, and time in local timezone"),
        ("get_weather",          "`get_weather` → `{\"city\":\"Mumbai\"}` — live current weather (temp, humidity, wind, conditions)"),
        ("get_news",             "`get_news` → `{\"topic_or_location\":\"Muzaffarnagar\"}` — live city/topic news"),
        ("answer_general_question", "`answer_general_question` → `{\"query\":\"who won the cricket match yesterday\"}` — live web search"),
    ]
    info_entries = [desc for name, desc in info_tools if _include(name)]
    if info_entries:
        lines += ["", "LIVE KNOWLEDGE, NEWS & UTILITIES (READ-ONLY):"] + info_entries

    # Coding tools
    code_tools = [
        ("open_vscode_and_write_code",  "`open_vscode_and_write_code` → `{\"filename\":\"main.py\",\"code\":\"...\"}` — DEFAULT for writing code, scripts, or programs"),
        ("open_notepad_and_write_code", "`open_notepad_and_write_code` → `{\"filename\":\"notes.txt\",\"code\":\"...\"}` — ONLY when user explicitly asks for Notepad or notes"),
        ("write_and_run_sandbox_code",  "`write_and_run_sandbox_code` → `{\"language\":\"python\",\"code\":\"...\",\"auto_run\":true}`"),
    ]
    code_entries = [desc for name, desc in code_tools if _include(name)]
    if code_entries:
        lines += ["", "CODE TOOLS (DEFAULT to open_vscode_and_write_code for code; use open_notepad_and_write_code ONLY for explicit text notes):"] + code_entries

    # Communication & Messaging tools
    comm_tools = [
        ("open_whatsapp_chat",             "`open_whatsapp_chat` → `{\"recipient\":\"Akhil Dondal\"}` — open, search, or focus a contact's chat in WhatsApp Desktop"),
        ("send_whatsapp_desktop_message", "`send_whatsapp_desktop_message` → `{\"recipient\":\"Akhil Dondal\",\"message\":\"hi\"}` — send message in WhatsApp Desktop"),
        ("send_whatsapp_message",         "`send_whatsapp_message` → `{\"recipient\":\"Vansh\",\"message\":\"hi\"}` — WhatsApp Web fallback"),
        ("check_whatsapp_notifications",  "`check_whatsapp_notifications` → `{}` — open WhatsApp Web"),
        ("delete_file",                   "`delete_file` → `{\"filename\":\"report.pdf\"}` — moves to trash with confirmation"),
        ("send_email",                    "`send_email` → `{\"recipient\":\"x@y.com\",\"subject\":\"Hi\",\"body\":\"...\"}` — opens mailto draft"),
    ]
    comm_entries = [desc for name, desc in comm_tools if _include(name)]
    if comm_entries:
        lines += ["", "COMMUNICATION & MESSAGING TOOLS:"] + comm_entries

    # WhatsApp rules (only if WhatsApp tools are in scope)
    if _include("send_whatsapp_desktop_message") or _include("open_whatsapp_chat"):
        lines += [
            "",
            "WHATSAPP ACTION RULES:",
            "- When user says 'open chat of X', 'show chat of X', 'search contact X', 'open chat once', or 'go to X chat' → ALWAYS output `[ACTION:{\"tool\":\"open_whatsapp_chat\",\"params\":{\"recipient\":\"X\"}}]`.",
            "- When user says 'send message M to X', 'write M to X', or 'say M to X' → ALWAYS output `[ACTION:{\"tool\":\"send_whatsapp_desktop_message\",\"params\":{\"recipient\":\"X\",\"message\":\"M\"}}]`.",
            "- If `send_whatsapp_desktop_message` returns AMBIGUOUS_RECIPIENT, ask the user to clarify. Do NOT guess.",
        ]

    # Multi-step examples (only relevant when browser tools included)
    if _include("navigate_to"):
        lines += [
            "",
            "MULTI-STEP WEB TASK EXAMPLES:",
            "- User: \"Find me flights from Delhi to Mumbai on MakeMyTrip\"",
            "  Step 1: [ACTION:{\"tool\":\"navigate_to\",\"params\":{\"url_or_search_query\":\"https://www.makemytrip.com/flights/\"},\"summary\":\"Navigate to MakeMyTrip\"}] Navigating now.",
        ]

    return "\n".join(lines) + "\n"

