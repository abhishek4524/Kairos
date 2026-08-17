"""
registry.py — Extensible Agentic Tools & Skills Registry for Kavya.

Defines schemas, execution metadata, and helper parsing for desktop OS tools.
"""

import json
import re

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open a desktop application on the user's computer (e.g. Spotify, Chrome, Notepad, Calculator, VS Code, Discord, Terminal).",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name or executable of the application (e.g. 'spotify', 'chrome', 'notepad', 'calc', 'code', 'discord', 'cmd')"
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
            "description": "Close or terminate a running desktop application on the user's computer (e.g. calculator, notepad, chrome, spotify, vs code).",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the application to close (e.g. 'calculator', 'notepad', 'chrome', 'calc', 'code')"
                    }
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_and_play_youtube",
            "description": "Search YouTube and play a song or video in the user's default web browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query, song name, or video title to play on YouTube"
                    }
                },
                "required": ["query"]
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
                        "description": "Filename with extension (e.g. 'solution.py', 'script.js', 'index.html')"
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
            "name": "check_whatsapp_notifications",
            "description": "Access WhatsApp to check unread messages or notifications. (Sensitive action: requires user confirmation).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["check_unread", "open_chat"],
                        "description": "Action to perform on WhatsApp"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_and_run_sandbox_code",
            "description": "Write code into Kavya's live Monaco code sandbox and execute it in an isolated subprocess.",
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
    """
    Formats the available tools into a clear system prompt instruction.
    Allows LLMs to emit action tags or invoke tools seamlessly.
    """
    return """
## DESKTOP TOOLS & ACTIONS (AGENTIC CAPABILITIES):
You have access to real desktop tools on the user's computer. When the user requests an action (opening an app, playing music on YouTube, writing code in VS Code, testing code in the sandbox, or checking WhatsApp), you MUST include an [ACTION:{...}] tag at the start of your response.

Available Actions:
1. Open Application:
   [ACTION:{"tool":"open_app","params":{"app_name":"spotify"},"summary":"Open Spotify"}]
   Supported apps: spotify, chrome, brave, notepad, calc (calculator), code (VS Code), discord, terminal, explorer (file explorer), etc.

2. Close Application:
   [ACTION:{"tool":"close_app","params":{"app_name":"calc"},"summary":"Close Calculator"}]

3. Play/Search YouTube:
   [ACTION:{"tool":"search_and_play_youtube","params":{"query":"Code with Harry"},"summary":"Search 'Code with Harry' on YouTube"}]

3. Write Code & Open in VS Code:
   [ACTION:{"tool":"open_vscode_and_write_code","params":{"filename":"solution.py","code":"def solve():\\n    print('Hello World')"},"summary":"Write solution.py in VS Code"}]

4. Live Code Sandbox (Monaco Editor & Subprocess Execution):
   [ACTION:{"tool":"write_and_run_sandbox_code","params":{"language":"python","code":"def two_sum(nums, target):\\n    d = {}\\n    for i, n in enumerate(nums):\\n        if target - n in d:\\n            return [d[target - n], i]\\n        d[n] = i\\n\\nprint(two_sum([2, 7, 11, 15], 9))","auto_run":true,"filename":"two_sum.py"},"summary":"Run 2Sum solution in Code Sandbox"}]

5. WhatsApp Notifications (Sensitive - user will be asked for confirmation):
   [ACTION:{"tool":"check_whatsapp_notifications","params":{"action":"check_unread"},"confirmation":true,"summary":"Check WhatsApp notifications"}]

6. Toggle Room Desk Lamp / Light:
   [ACTION:{"tool":"toggle_room_light","params":{"state":"on"},"summary":"Turn on desk lamp"}]
   (state can be 'on' or 'off')

7. Sit on Chair / Stand Up:
   [ACTION:{"tool":"sit_on_chair","params":{},"summary":"Sit on chair"}]
   [ACTION:{"tool":"stand_up","params":{},"summary":"Stand up"}]

8. Read a Book / Put Book Down:
   [ACTION:{"tool":"read_book","params":{},"summary":"Walk to bookshelf and read a book"}]
   [ACTION:{"tool":"put_book_down","params":{},"summary":"Put book down and return to center"}]

9. Jump:
   [ACTION:{"tool":"jump","params":{},"summary":"Jump in place"}]

RULES:
- When a user asks you to do any of these things, always output the [ACTION:{...}] tag right after the emotion/gesture tag.
- Follow with a SHORT confirmation — 1 sentence only. Examples:
  - "Opening YouTube now!" 
  - "Playing that on YouTube!"
  - "Done, VS Code is opening with your code."
- Do NOT write a paragraph explaining what you did. One sentence is enough.
- Do not output the action tag if the user is just chatting or asking a theoretical question.
"""
