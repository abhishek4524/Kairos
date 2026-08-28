# Kairos — Autonomous Desktop AI Assistant & Living Neural Core

<div align="center">

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![React](https://img.shields.io/badge/React_18-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Three.js](https://img.shields.io/badge/Three.js-000000?style=for-the-badge&logo=three.js&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Memory-orange?style=for-the-badge)
![Groq](https://img.shields.io/badge/Groq-LPUs_Ultra_Fast-F55036?style=for-the-badge)
![Electron](https://img.shields.io/badge/Electron-Desktop_App-47848F?style=for-the-badge&logo=electron)

**An ultra-fast, real-time voice-interactive personal AI assistant powered by a 3D Living Neural Core, long-term vector memory, autonomous multi-browser automation (Brave & Chrome CDP), and voice-to-code execution.**

</div>

---

## 🌟 Key Capabilities & Features

### 🧠 1. 3D Living Neural Core Centerpiece
- **11-State Real-Time Machine:** Reflects internal cognitive phases — `IDLE`, `LISTENING`, `PROCESSING_INPUT`, `THINKING`, `GENERATING`, `MEMORY_UPDATE`, `RAG_INGESTION`, `RAG_RETRIEVAL`, `TOOL_EXECUTION`, `SUCCESS`, and `ERROR`.
- **Refined Geodesic Geometry:** Wireframe icosahedron nucleus with counter-rotating inner shell, instanced synaptic nodes, and directional signal particle streams.
- **Audio-Reactive Synced Pulses:** 3D core breathing, dynamic scaling, and particle radiation driven by live `AnalyserNode` audio waveforms throughout speech.
- **Fluid 3D Mouse Controls:** Smooth OrbitControls with damping, mouse wheel zoom (`1.0x`–`25.0x`), right-click pan, quick on-screen zoom toolbar (`[+]`, `[-]`, `[↺ Reset]`), and perspective presets (`GALAXY`, `CORE`, `MEMORY`).

### 🤖 2. Autonomous Multi-Browser & Desktop Automation
- **Dual Browser Target Support (Brave & Google Chrome):**
  - **Brave CDP Automation (Port 9222):** Default general browsing and YouTube target with coordinate-free element resolution.
  - **Google Chrome CDP Automation (Port 9223):** Isolated browser profile dedicated to Work Mode and custom web workflows.
- **Work Mode Launcher (`work_mode`):**
  - *"Activate work mode"* / *"Work mode on"* → Launches Google Chrome via CDP on port 9223, opens GitHub, LeetCode, Gmail, and ChatGPT in separate tabs, verifies each tab's title/URL post-navigation, and launches VS Code in the configured default workspace.
  - **Configurable Site Targets:** Customizable via `backend/config/work_mode_sites.py` or `KAIROS_WORK_MODE_SITES` env var.
- **Standalone Launchers:**
  - *"Open Brave"* (`open_brave`) → Direct, fast launch or focus of Brave browser with zero CDP overhead.
  - *"Open VS Code"* (`open_vscode`) → Launches Visual Studio Code on desktop.
- **YouTube Autonomous Navigation:**
  - *"Open YouTube"* → Launches YouTube inside Brave.
  - *"Search [topic]"* → Automatically searches YouTube for the topic.
  - *"Play 1st / 2nd / 3rd video"* → Calculates precise thumbnail coordinates, focuses window, clicks, and starts video playback.
- **Full Media & Page Controls:**
  - *"Scroll down / Scroll up"* → Smooth automated page scrolling.
  - *"Pause / Play / Mute / Fullscreen"* → Instant keyboard media shortcuts.
- **Voice-to-Code Generation:**
  - *"Write Python code in Notepad"* (`open_notepad_and_write_code`) → Creates a file and immediately opens it in Notepad with the generated code.
  - *"Write code in VS Code"* (`open_vscode_and_write_code`) → Creates a workspace file and opens it in Visual Studio Code.
  - *"Run in sandbox"* (`write_and_run_sandbox_code`) → Injects code into the live Monaco editor sandbox.

### ⚡ 3. Ultra-Fast LLM Reasoning (~0.74s Latency)
- **Primary Engine:** Qwen 3.8 27B on Groq LPUs for sub-second responses and tool execution.
- **Fallback Engine:** NVIDIA NIM (`meta/llama-3.1-8b-instruct`) for resilient high-availability.
- **Context Management:** Dynamic history windowing (last 6 turns) + compact 534-token tool prompt to eliminate token overflow (`Request Entity Too Large`).
- **Action Tag Sanitization:** Automatically strips `[ACTION:{...}]` tags before saving to persistent history, preventing tool actions from re-triggering upon reload or reconnection.

### 🌍 4. Jarvis-Style Live World Intelligence (No Hallucinations)
- **Real-Time Date & Time (`get_current_datetime`):** Detects system local timezone automatically, supports `KAIROS_TIMEZONE` override. Responds in natural English (*"Today is Thursday, August 27, 2026, and the time is 10:30 AM IST"*).
- **Hyperlocal & Global News (`get_news`):** Fetches top 3–5 live headlines for any topic or location via Google News RSS (no API key needed). Excellent coverage of Indian cities/states (Muzaffarnagar, Uttar Pradesh, Delhi) and global topics (tech, business, world).
- **Live Web Q&A (`answer_general_question`):** Routes through Tavily Search API (or DuckDuckGo fallback) to answer any live question — cricket scores, weather, facts, current events — in 2–4 spoken sentences.
- **5-10 Minute TTL Caching:** Repeated voice queries served from in-memory cache to save API quota without latency.
- **Honest Failure Handling:** If network/API fails, speaks a clear refusal (*"I couldn't fetch live news for that topic right now"*) — never hallucinates from stale training data.
- **Multilingual Routing:** Handles natural Hindi/Hinglish/English queries (*"aaj ki date kya hai"*, *"Muzaffarnagar ki news bata"*, *"kal ka match kisne jeeta"*).

### 🎙️ 4. Real-Time Streaming Voice Engine
- **Ultra-Low Latency WebSocket Pipeline:** Full-duplex audio chunk streaming between React frontend and FastAPI backend.
- **Local STT (Faster-Whisper):** Real-time speech-to-text with CUDA acceleration and Voice Activity Detection (Silero VAD / RMS energy fallback).
- **Male Neural TTS:** Edge-TTS powered voice synthesis featuring `en-US-ChristopherNeural` (crisp, authoritative, intelligent AI voice).
- **Barge-In Interruption:** Voice activity instantly cancels the in-flight TTS response for natural conversation flow.

### 📚 5. Long-Term Vector Memory & Document RAG
- **Episodic Fact Extraction:** Non-blocking async background worker automatically extracts salient user facts from conversation turns and stores them in ChromaDB.
- **ChromaDB Knowledge Retrieval:** Ingest PDFs, markdown notes, and text files into vector storage with semantic chunk search.
- **Memory Management Panel:** Pin critical facts to always inject into context, inspect chunk similarity scores, or delete items on demand.

### 🖥️ 6. Zero-Conflict Electron Desktop Integration
- **Smart Backend Supervisor:** Detects if a backend is already running on port 8000 (e.g. manual `uvicorn` during development) and automatically connects to it without port binding errors.
- **Secure ContextBridge (`window.kavya`):** Provides safe IPC bridges for window minimization, maximization, close, sandboxed command execution, and file creation.

---

## 🏗️ Architecture Overview

```
Personal Assistant (Kairos)/
├── frontend/                     # React 18 + Vite + TailwindCSS + Three.js
│   ├── neural/                   # 3D Living AI Core & State Engine
│   │   ├── LivingAICoreCanvas.jsx# WebGL Scene, OrbitControls, Audio Analyser
│   │   ├── NeuralController.js   # Three.js InstancedMesh & Particle Simulation
│   │   ├── neuralStateMachine.js # 11-State Event Bus & Visual Profiles
│   │   └── ModelInfoHUD.jsx      # Telemetry & Hyperparameter HUD
│   ├── components/               # Glassmorphic UI Components
│   │   ├── chat/                 # Chat Panel, History, Streaming Bubbles
│   │   ├── layout/               # AppLayout, VoiceDock, ElectronTitleBar
│   │   ├── memory/               # ChromaDB Memory & Document Ingestion
│   │   ├── sandbox/              # Monaco Code Sandbox
│   │   └── settings/             # System Configuration & Telemetry
│   └── hooks/
│       └── useAudioStreaming.js  # WebSocket audio streaming & Web Audio API
├── backend/                      # FastAPI Backend
│   ├── main.py                   # WebSocket stream router, VAD, Task queue
│   ├── llm_agent.py              # Kairos Persona, Groq/NVIDIA LLM reasoning
│   ├── fact_extractor.py         # Async episodic user fact extractor
│   ├── tts_agent.py              # Male Neural Edge-TTS engine
│   ├── db.py                     # Local SQLite conversation persistence
│   ├── chroma_db/                # ChromaDB vector store & embeddings
│   ├── config/                   # Path and target configurations
│   │   ├── platform_paths.py     # Cross-platform Brave, Chrome, VS Code resolvers
│   │   └── work_mode_sites.py    # Configurable Work Mode sites and workspace
│   ├── agents/                   # Orchestrator & Specialized Sub-Agents
│   │   ├── orchestrator.py       # Intent router (<150ms classification)
│   │   ├── browsing_agent.py     # Web & YouTube sub-agent
│   │   ├── coding_agent.py       # Code generation & VS Code sub-agent
│   │   └── system_agent.py       # Desktop & OS control sub-agent
│   └── agent_tools/              # Desktop automation tool registry & executor
│       ├── browser.py            # Playwright CDP automation (Brave 9222 / Chrome 9223)
│       ├── registry.py           # Compact schema definitions & system prompt
│       ├── permissions.py        # Security allowlist & two-step confirmation
│       └── executor.py           # Subprocess-isolated PyAutoGUI & OS tools
├── electron/                     # Electron Desktop Wrapper
│   ├── main.js                   # Main process, auto-detecting backend runner
│   ├── preload.js                # Secure ContextBridge (`window.kavya`)
│   └── assets/                   # App icon and window assets
└── package.json                  # Root runner & build scripts
```

---

## 🚀 Quick Start

### Prerequisites
- **Node.js**: v18.0.0 or later
- **Python**: 3.10 to 3.13
- **Groq API Key** (Set `GROQ_API_KEY` in environment or `backend/.env`)
- **Brave Browser & Google Chrome** (Installed on Windows, macOS, or Linux)

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/abhishek4524/Kairos.git
cd "Personal Assistant"

# Install root & frontend dependencies
npm run setup

# Install Python backend dependencies
cd backend
python -m venv venv

# Windows:
.\venv\Scripts\pip install -r requirements.txt

# macOS / Linux:
./venv/bin/pip install -r requirements.txt

cd ..
```

### 2. Environment Configuration
Create a `.env` file in `backend/`:
```env
# ── Core AI Keys ──
GROQ_API_KEY=your_groq_api_key_here
NVIDIA_API_KEY=optional_nvidia_nim_fallback_key
PORT=8000

# ── Cross-Platform Browser & Executable Paths (Optional) ──
# Brave browser executable override:
KAIROS_BRAVE_PATH=
# Google Chrome executable override:
KAIROS_CHROME_PATH=
# Visual Studio Code executable / command:
KAIROS_VSCODE_PATH=
# Custom Python venv interpreter path:
KAIROS_PYTHON_PATH=

# ── Work Mode & CDP Port Configuration ──
# CDP port for Brave browser automation (default 9222):
KAIROS_CDP_PORT=9222
# CDP port for Google Chrome Work Mode automation (default 9223):
KAIROS_CHROME_CDP_PORT=9223
# Default workspace folder opened in VS Code during Work Mode (default ~/KairosWorkspace):
KAIROS_DEFAULT_WORKSPACE=
# Custom JSON array of Work Mode sites:
KAIROS_WORK_MODE_SITES=

# ── Live Knowledge, News & Web Search (Optional) ──
# Tavily Search API key for real-time web search Q&A (get free key at https://tavily.com):
KAIROS_SEARCH_API_KEY=
# Display timezone override for date/time queries (default: system local timezone, e.g. Asia/Kolkata):
KAIROS_TIMEZONE=
```

### 3. Run in Development Mode
```bash
# Option A: Run Electron Desktop App
cd electron
npm run dev

# Option B: Run Backend Separately (with hot-reload)
cd backend
# Windows:
.\venv\Scripts\uvicorn main:app --reload --port 8000
# macOS / Linux:
./venv/bin/uvicorn main:app --reload --port 8000

# Open frontend in browser:
cd frontend
npm run dev
# Visit http://localhost:5173
```

---

## 🗣️ Voice Commands Quick Reference

### 🌐 Browser & Automation
| Voice Command | Tool Triggered | Action Performed |
|---|---|---|
| *"Activate work mode"* / *"Work mode on"* | `work_mode` | Launches **Google Chrome** via CDP (port 9223), opens GitHub, LeetCode, Gmail, and ChatGPT in separate tabs, verifies each tab loaded, and opens **VS Code** in the default workspace. |
| *"Open Brave"* / *"Launch Brave"* | `open_brave` | Standalone launcher that opens or focuses the **Brave Browser** with no further action. |
| *"Open VS Code"* / *"Open Code"* | `open_vscode` | Standalone launcher that opens **Visual Studio Code** on desktop with no workspace arguments. |
| *"Open YouTube"* | `open_youtube_in_brave` | Opens YouTube in Brave browser. |
| *"Search [topic]"* | `youtube_search` | Searches YouTube for the requested topic inside Brave. |
| *"Play 1st video"* / *"Play 2nd video"* | `youtube_play_video` | Clicks and plays the N-th YouTube search result. |
| *"Scroll down"* / *"Scroll up"* | `scroll_page` | Smoothly scrolls the active web page. |
| *"Pause video"* / *"Play video"* | `youtube_control` | Toggles YouTube playback. |
| *"Write a simple code of Python in Notepad"* | `open_notepad_and_write_code` | Generates Python code and opens it in Notepad. |
| *"Write a react component in VS Code"* | `open_vscode_and_write_code` | Creates a code file in the workspace and opens it in VS Code. |
| *"Run code in sandbox"* | `write_and_run_sandbox_code` | Writes code and executes it in Kairos's Monaco sandbox. |

### 🌍 Live World Intelligence (Real-Time, No Hallucination)
| Voice Command (English) | Hinglish Example | Tool Triggered | Action |
|---|---|---|---|
| *"What's today's date?"* / *"What time is it?"* | *"Aaj date kya hai?"* / *"Time kya hua hai?"* | `get_current_datetime` | Returns real-time date, day of week, and local time with timezone. |
| *"Muzaffarnagar news today"* / *"Tech news today"* | *"Aaj ki Muzaffarnagar ki news bata"* / *"UP ki news sunao"* | `get_news` | Fetches and reads top 3–5 live headlines from Google News RSS (hyperlocal Indian + global). |
| *"World news"* / *"Top headlines"* | *"Aaj ki world news bata"* | `get_news` | Fetches top global headlines from Google News RSS. |
| *"Who won the match yesterday?"* / *"What's new in AI?"* | *"Kal ka match kisne jeeta?"* | `answer_general_question` | Live web-search backed answer (Tavily → DuckDuckGo fallback), 2–4 spoken sentences. |

---

## 🔌 Electron IPC Context Bridge (`window.kavya`)

| Method | Description |
|---|---|
| `window.kavya.minimize()` | Minimizes application window |
| `window.kavya.maximize()` | Toggles maximize / restore window |
| `window.kavya.close()` | Gracefully closes app and cleans up child processes |
| `window.kavya.isMaximized()` | Checks current window state |
| `window.kavya.executeTool(toolName, params)` | Dispatches OS automation tool |
| `window.kavya.writeFile(filename, content)` | Writes file in user workspace |
| `window.kavya.runCommand(cmd, args, opts)` | Runs sandboxed command on local system |
| `window.kavya.openExternal(url)` | Opens link in default browser |

---

## 🤖 Kairos Persona & Behavior Guidelines
- **Name:** Kairos
- **Identity:** Abhishek's loyal, smart, and friendly personal AI assistant.
- **Language Policy:** Accepts input in any language (English, Hindi, Hinglish); responds in **100% natural, clear English voice and text**.
- **Tone:** Concise, helpful, intelligent, and proactive.

---

## 🧪 Running Automated Tests

Kairos includes a test suite with **pytest** covering browser automation, standalone launchers, Work Mode CDP integration, the security permission engine, and the WebSocket voice pipeline.

```bash
cd backend
python -m pytest tests/test_work_mode_and_launchers.py tests/test_tool_executor.py tests/test_platform_paths.py tests/test_browser_suite.py -v
```

### Test Suite Structure

| Test File | What it covers |
|---|---|
| [`test_work_mode_and_launchers.py`](backend/tests/test_work_mode_and_launchers.py) | Work Mode (Chrome CDP 9223, 4 sites + VS Code), partial failure handling, standalone launchers (`open_brave`, `open_vscode`), missing binary error reporting, port isolation |
| [`test_tool_executor.py`](backend/tests/test_tool_executor.py) | All registered tools with mocked browser/subprocess calls |
| [`test_platform_paths.py`](backend/tests/test_platform_paths.py) | Cross-platform Brave, Chrome, VS Code, and Python path resolvers |
| [`test_browser_suite.py`](backend/tests/test_browser_suite.py) | Browser primitive schemas, ordinal extraction, element resolver |
| [`test_permissions.py`](backend/tests/test_permissions.py) | Allowlist enforcement, path traversal, shell injection, 2-step confirmation |
| [`test_protected_zone.py`](backend/tests/test_protected_zone.py) | System path protection, credential patterns, financial hard-blocks |

---

## 🛡️ License
Built with passion by **Abhishek Kumar** (`@abhishek4524`). All rights reserved.
