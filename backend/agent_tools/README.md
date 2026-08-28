# Kairos Browser & Desktop Automation (`backend/agent_tools`)

This directory houses the automation subsystems for Kairos, providing generic, multi-step browser control over Chrome DevTools Protocol (CDP) and desktop OS automation.

---

## 1. Browser Automation Architecture (CDP + Playwright)

Browser control uses **Playwright** connected over **Chrome DevTools Protocol (CDP)** directly to a running **Brave Browser** instance.

- **No pixel coordinate guessing**: All element interactions (`click`, `type`, `scroll`, `read`) are performed via real DOM inspection, accessibility trees, ARIA attributes, and semantic element locators.
- **Dedicated Worker Thread**: Playwright operations execute inside a dedicated background worker thread (`BrowserManager._executor`), eliminating event loop collisions with FastAPI's `asyncio` loop.
- **Live Tab Reuse**: Attaches to the active Brave instance rather than creating isolated incognito automation contexts, preserving existing cookies, logins, and session state.

---

## 2. Remote Debugging Setup & Auto-Launch

Kairos automatically attempts to detect and connect to Brave on the configured CDP port:

- **Default Port**: `9222`
- **Environment Variable Override**: `KAIROS_CDP_PORT` (e.g. `KAIROS_CDP_PORT=9222`)

### Auto-Launch Behavior
1. Checks `http://127.0.0.1:<PORT>/json/version`.
2. If unreachable, launches Brave with:
   ```cmd
   brave.exe --remote-debugging-port=9222 --remote-allow-origins=* --no-first-run
   ```
3. Waits up to 6 seconds for the CDP socket to open and connects.

### Manual Setup (If Auto-Launch Fails)
If Brave is already running without remote debugging enabled, or if you prefer to launch Brave manually:

1. Close all running Brave instances:
   ```powershell
   taskkill /IM brave.exe /F
   ```
2. Start Brave from terminal with remote debugging enabled:
   ```cmd
   "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" --remote-debugging-port=9222 --remote-allow-origins=*
   ```
3. Verify the CDP endpoint is active by opening `http://127.0.0.1:9222/json/version` in any browser or curl.

---

## 3. Generic Browser Primitives

| Primitive | Parameters | Description |
|---|---|---|
| `navigate_to` | `url_or_search_query` (string) | Navigates to a direct URL (e.g., `https://en.wikipedia.org`) or performs a web search if given query terms. |
| `find_and_click` | `description` (string) | Resolves elements via role, text, ARIA label, ordinal position (e.g., "second link", "submit button"), or smart DOM heuristic scan and clicks it. |
| `type_into` | `description` (string), `text` (string), `press_enter` (bool) | Finds an input, textarea, or search field matching the description and types the text. |
| `scroll_page` | `direction` ("down"/"up"), `amount` (int, default 500) | Smoothly scrolls the active page. |
| `extract_page_text` / `read_page` | `max_chars` (int, default 3000) | Extracts clean text content, page title, URL, and a snapshot of interactive elements for summarization and LLM reasoning. |
| `go_back` | *none* | Navigates back in browser history. |
| `open_new_tab` | `url` (string, optional) | Opens a new browser tab. |
| `switch_tab` | `index_or_description` (int or string) | Switches active tab by index or title/URL matching. |

### Backward-Compatibility Shortcuts
- `open_youtube_in_brave(query)`
- `youtube_search(query)`
- `youtube_play_video(index)`
- `youtube_control(action)`

These legacy commands are implemented as thin wrappers over the generic CDP primitives and no longer rely on PyAutoGUI coordinate calculations.

---

## 4. Visual & Textual Confirmation Channel

Each mutating action (`find_and_click`, `type_into`, `navigate_to`, `extract_page_text`) returns a structured `confirmation` dictionary:

```json
{
  "success": true,
  "message": "Clicked <button> 'Book Flight'.",
  "url": "https://...",
  "title": "Search Results",
  "confirmation": {
    "action": "clicked",
    "description": "Book Flight",
    "element": {
      "tag": "button",
      "text": "Book Flight",
      "aria_label": "Book Flight Now",
      "id": "book-btn-01",
      "box": { "x": 420, "y": 680, "width": 140, "height": 44 }
    },
    "url_after": "https://..."
  }
}
```

This confirmation payload is emitted in the WebSocket `tool_result` event, allowing the **Plan → Execute → Reflect** agent loop to verify that intended actions succeeded before proceeding to the next step.

---

## 5. Desktop OS Automation (PyAutoGUI)

PyAutoGUI is reserved strictly for non-browser desktop management:
- `open_app(app_name)` / `close_app(app_name)`
- `cursor_control(action, x, y, text, key)` (Desktop coordinates/clicks)
- `type_in_active_window(text)`
- `open_notepad_and_write_code` / `open_vscode_and_write_code`

---

## 6. Native Desktop App Automation (UIA / Accessibility API)

Kairos supports native desktop UI automation via platform-specific Accessibility and UI Automation APIs, allowing it to automate applications (such as the native WhatsApp Desktop standalone client) that cannot be controlled via browser CDP.

### Primitives
- `send_whatsapp_desktop_message(recipient, message)`: Opens/focuses the native WhatsApp Desktop application, searches for the recipient, resolves the contact, types the message, clicks the send button, and verifies the sent message.

### Technical Implementation & Platforms
- **Windows (`pywinauto` - UIA Backend)**:
  - Connects to a running WhatsApp instance or launches it via `whatsapp:` URI schema.
  - Recursively scans the UIA tree for edit boxes (e.g., named "Search" or of control type "Edit"), contact items (e.g. `ListItem` or `Button` matching contact name), and send buttons.
- **macOS (`atomacos` - Accessibility API)**:
  - Automates elements via macOS native Cocoa accessibility nodes (`AXTextField`, `AXButton`, `AXTextArea`).
- **Linux (Graceful Fallback)**:
  - Native automation of packaged chat clients varies significantly across distributions (Snap, Flatpak, native packages). Kairos detects Linux and gracefully falls back to guiding the user to use the browser-based WhatsApp Web tool (`send_whatsapp_message`) instead.

### Key Features
1. **Contact Disambiguation**:
   If a search query yields multiple matching contacts (e.g., searching for "Vansh" returns "Vansh Kumar" and "Vansh Sharma"), the tool returns `AMBIGUOUS_RECIPIENT` alongside a list of matches. The LLM then prompts the user to select the correct contact before continuing.
2. **Two-Step Confirmation Integration**:
   This tool is fully integrated with the Security Permission Engine (`permissions.py`). Like WhatsApp Web and Email, the native send button is only invoked after the user explicitly reviews the message body and says "yes" or "send it".
3. **Sent Verification**:
   After triggering the send, Kairos scans the UI tree and reads back the text of the last message bubble (via the accessibility name or static text values) to verify the sent text matches the intended message.

### Version-Specific Quirks & Fallbacks
- **Search and Input Box Heuristics**: WhatsApp Desktop layout (UWP App vs Win32 installer) varies slightly. If search or text inputs with specific labels like "Type a message" cannot be found, the driver falls back to finding the first available edit control (for search) or the last available edit/document control (for text input).
- **Send Trigger Fallback**: If a button named "Send" is missing or unmapped in the accessibility tree, the automation falls back to sending a `{ENTER}` keyboard event inside the message field.

