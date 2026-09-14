# Kairos — Autonomous Desktop AI Assistant & Living Neural Core

<div align="center">

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![React](https://img.shields.io/badge/React_18-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Three.js](https://img.shields.io/badge/Three.js-000000?style=for-the-badge&logo=three.js&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-MediaPipe_Hands-blue?style=for-the-badge&logo=opencv)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Memory-orange?style=for-the-badge)
![Groq](https://img.shields.io/badge/Groq-LPUs_Ultra_Fast-F55036?style=for-the-badge)
![Electron](https://img.shields.io/badge/Electron-Desktop_App-47848F?style=for-the-badge&logo=electron)

**An ultra-fast, real-time voice-interactive personal AI assistant powered by a 3D Living Neural Core, Stark Hologram Camera Gesture Control, long-term vector memory, autonomous multi-browser automation (Brave & Chrome CDP), and voice-to-code execution.**

</div>

---

## 🌟 Key Capabilities & Features

### 🚀 1. Stark Hologram & Cyberpunk Camera Hand Gesture Control
- **Dual Operating Modes:**
  - **`💻 System Control`**: Adjusts system screen brightness with your Right Hand (OPEN = Up, CLOSED = Down) and master volume with your Left Hand (OPEN = Up, CLOSED = Down) via thread-safe Windows COM pycaw integration.
  - **`🎭 3D Model Control` (Holo Matrix)**: Interactively manipulates the 3D Neural AI Core directly in air like Iron Man / Minority Report.
- **Sci-Fi Multi-Gesture Suite:**
  - **Iron Man Repulsor Blast** 💥: Extend all 5 fingers facing the camera to trigger an instant energy pulse shockwave on the 3D Neural Core.
  - **Stark Hologram Span Scaling** 👐: Move both palms apart to expand/zoom the 3D Hologram, or push them together to contract it. Renders a live laser line connecting your palms with real-time distance readouts (`⚡ HOLO SPAN: 42cm`).
  - **3D Spatial Air Drag** 🖐️: Move your hand across the room in 3D air — the 3D Neural Core tracks your physical hand coordinates and tilts/rotates smoothly in space.
  - **Pinch-to-Drag** 👌: Detects thumb + index tip pinch (`dist < 0.065m`) for fine spatial manipulation.
- **Cyberpunk Camera Stream HUD (`/api/gesture/stream`):**
  - Live MJPEG video stream rendered directly inside a floating glassmorphic widget (`GesturePreview.jsx`) at the top-left of the screen.
  - Cyberpunk corner reticles (`┌ ┐ └ ┘`), dual neon fingertip target rings (`cyan` & `magenta`), and live telemetry header overlay.
- **Floating UI Controller (`GesturePreview.jsx`):**
  - Includes a mode switch pill button (`[ 💻 System / 🎭 3D Model ]`), camera fold/unfold button, and camera start/stop button.

### 🧠 2. 3D Living Neural Core Centerpiece
- **11-State Real-Time Machine:** Reflects internal cognitive phases — `IDLE`, `LISTENING`, `PROCESSING_INPUT`, `THINKING`, `GENERATING`, `MEMORY_UPDATE`, `RAG_INGESTION`, `RAG_RETRIEVAL`, `TOOL_EXECUTION`, `SUCCESS`, and `ERROR`.
- **Refined Geodesic Geometry:** Wireframe icosahedron nucleus with counter-rotating inner shell, instanced synaptic nodes, and directional signal particle streams.
- **Audio-Reactive Synced Pulses:** 3D core breathing, dynamic scaling, and particle radiation driven by live `AnalyserNode` audio waveforms throughout speech.
- **Fluid 3D Mouse & Gesture Controls:** OrbitControls with damping, mouse wheel zoom (`1.0x`–`25.0x`), right-click pan, camera presets (`GALAXY`, `CORE`, `MEMORY`), and full hand-gesture manipulation support.

### 🎭 3. Dual Persona & Mode Switching (Arya Persona)
- **GF Mode (Default):** Friendly, warm, affectionate, caring AI partner persona (responds in 100% natural, clear English voice and text).
- **Assistant Mode:** Precise, objective, technical, and executive personal assistant persona.
- **Voice & UI Persona Switching:** Switch seamlessly via voice ("Switch to assistant mode", "Switch to GF mode") or via UI toggle buttons on VoiceDock, ChatPanel, and TelemetrySidebar.

### 🤖 4. Autonomous Multi-Browser & Desktop Automation
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

### ⚡ 5. High-Performance LLM Engine & Resilient Router
- **Primary Engine:** Groq LPUs (`qwen-2.5-32b` / `llama-3.3-70b-versatile`) for ultra-low latency sub-second reasoning and tool calling.
- **Fallback Engine:** NVIDIA NIM (`01-ai/yi-large` / `meta/llama-3.1-8b-instruct`) for high-availability backup.
- **Context Management:** Dynamic history windowing (last 6 turns) + compact token tool prompt to eliminate token overflow (`Request Entity Too Large`).
- **Action Tag Sanitization:** Automatically strips `[ACTION:{...}]` tags before saving to persistent history, preventing tool actions from re-triggering upon reload or reconnection.

### 🎙️ 6. Hybrid Neural Voice Engine (ElevenLabs + Edge-TTS)
- **Ultra-Low Latency WebSocket Pipeline:** Full-duplex audio chunk streaming between React frontend and FastAPI backend.
- **Local STT (Faster-Whisper):** Real-time speech-to-text with CUDA acceleration and Voice Activity Detection (Silero VAD / RMS energy fallback).
- **ElevenLabs Primary TTS:** Connects to ElevenLabs TTS API (`ELEVENLABS_VOICE_ID`).
- **Edge-TTS Auto Fallback:** If ElevenLabs key is invalid or out of quota, automatically falls back to Edge-TTS (`en-US-AvaNeural` / `en-US-ChristopherNeural`) with zero interruption.
- **Barge-In Interruption:** Voice activity instantly cancels the in-flight TTS response for natural conversation flow.

### 🌍 7. Jarvis-Style Live World Intelligence (No Hallucinations)
- **Real-Time Date & Time (`get_current_datetime`):** Detects system local timezone automatically, supports `KAIROS_TIMEZONE` override. Responds in natural English (*"Today is Thursday, August 27, 2026, and the time is 10:30 AM IST"*).
- **Hyperlocal & Global News (`get_news`):** Fetches top 3–5 live headlines for any topic or location via Google News RSS (no API key needed). Coverage of Indian cities/states and global topics.
- **Live Web Q&A (`answer_general_question`):** Routes through Tavily Search API (or DuckDuckGo fallback) to answer live questions in 2–4 spoken sentences.
- **Multilingual Input Routing:** Handles natural Hindi/Hinglish/English voice queries (*"aaj ki date kya hai"*, *"Muzaffarnagar ki news bata"*); AI always responds in **100% natural, clear English voice and text**.

### 📚 8. Unified Multi-Format Document Ingestion & Vector RAG
- **Supported Formats:** PDF, Word (`.docx`), CSV, Excel (`.xlsx`), Images (`.jpg`/`.png`), TXT, Markdown.
- **Spreadsheet Analytics (`query_spreadsheet`):** Ingested CSV/XLSX workbooks retain DataFrames in memory so Kairos executes exact pandas calculations (sums, averages, stats) for numeric questions instead of relying solely on text RAG chunks.

---

## 📑 Supported File Types Matrix

| File Format | Extensions | Primary Library | Optional System Dependency |
|---|---|---|---|
| **PDF** | `.pdf` | `pypdf` / `pdfplumber` | Tesseract OCR + Poppler (for scanned PDFs) |
| **Word** | `.docx`, `.doc` | `python-docx` | None (warns on legacy `.doc`) |
| **CSV** | `.csv` | `pandas` / `csv.Sniffer` | None |
| **Excel** | `.xlsx`, `.xls` | `openpyxl` via `pandas` | None |
| **Images** | `.jpg`, `.jpeg`, `.png`, `.bmp` | `Pillow` + `pytesseract` | Tesseract OCR system binary |
| **Text** | `.txt`, `.md`, `.json`, `.log` | Built-in UTF-8 reader | None |

---

## 🏗️ Architecture Overview

```
Personal Assistant (Kairos)/
├── frontend/                     # React 18 + Vite + TailwindCSS + Three.js
│   ├── neural/                   # 3D Living AI Core & State Engine
│   │   ├── LivingAICoreCanvas.jsx# WebGL Scene, Stark 3D Gestures, Audio Analyser
│   │   ├── NeuralController.js   # Three.js InstancedMesh & Particle Simulation
│   │   ├── neuralStateMachine.js # 11-State Event Bus & Visual Profiles
│   │   └── ModelInfoHUD.jsx      # Telemetry & Hyperparameter HUD
│   ├── components/               # Glassmorphic UI Components
│   │   ├── chat/                 # Chat Panel, History, Persona Switcher
│   │   ├── layout/               # AppLayout, GesturePreview, VoiceDock
│   │   ├── memory/               # ChromaDB Memory & Document Ingestion
│   │   ├── sandbox/              # Monaco Code Sandbox
│   │   └── settings/             # System Configuration & Telemetry
│   └── hooks/
│       └── useAudioStreaming.js  # WebSocket audio streaming & Web Audio API
├── backend/                      # FastAPI Backend
│   ├── main.py                   # WebSocket stream router, Gesture API, VAD
│   ├── llm_agent.py              # Kairos Persona Prompts, Groq/NVIDIA Router
│   ├── tts_agent.py              # ElevenLabs + Edge-TTS fallback synthesis engine
│   ├── db.py                     # Local SQLite conversation persistence
│   ├── chroma_db/                # ChromaDB vector store & embeddings
│   ├── config/                   # Path and target configurations
│   │   ├── platform_paths.py     # Cross-platform Brave, Chrome, VS Code resolvers
│   │   └── work_mode_sites.py    # Configurable Work Mode sites and workspace
│   ├── agent_tools/              # Desktop & Gesture automation tool registry
│   │   ├── gesture_control.py    # Camera Hand Gesture Controller & MediaPipe Tasks API
│   │   ├── browser.py            # Playwright CDP automation (Brave 9222 / Chrome 9223)
│   │   ├── registry.py           # Compact schema definitions & system prompt
│   │   ├── permissions.py        # Security allowlist & risk classification
│   │   └── executor.py           # Subprocess-isolated PyAutoGUI & OS tools
│   └── tools/
│       └── hand_landmarker.task  # MediaPipe Hand Landmarker model file
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
- **Webcam** (For Camera Gesture Control)

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
ELEVENLABS_API_KEY=optional_elevenlabs_key
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
PORT=8000

# ── Cross-Platform Browser & Executable Paths (Optional) ──
KAIROS_BRAVE_PATH=
KAIROS_CHROME_PATH=
KAIROS_VSCODE_PATH=
KAIROS_PYTHON_PATH=

# ── Work Mode & CDP Port Configuration ──
KAIROS_CDP_PORT=9222
KAIROS_CHROME_CDP_PORT=9223
KAIROS_DEFAULT_WORKSPACE=
KAIROS_WORK_MODE_SITES=

# ── Live Knowledge & Search ──
KAIROS_SEARCH_API_KEY=
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

### 🚀 Camera Hand Gesture Control
| Voice Command | Tool Triggered | Action Performed |
|---|---|---|
| *"Start camera gesture control"* | `start_camera_gesture_control` | Activates camera hand gesture tracking thread. |
| *"Stop camera gesture control"* | `stop_camera_gesture_control` | Stops camera gesture controller thread. |
| *"Switch gesture to 3D model mode"* | `set_camera_gesture_mode` | Switches mode to `avatar` (3D Model rotation, zoom, spatial drag, and repulsor blast). |
| *"Switch gesture to system mode"* | `set_camera_gesture_mode` | Switches mode to `system` (Screen Brightness & Master Volume control). |
| *"Check camera gesture status"* | `get_camera_gesture_status` | Returns current camera state, mode, brightness, volume, and hand telemetry. |

### 🌐 Browser & Automation
| Voice Command | Tool Triggered | Action Performed |
|---|---|---|
| *"Activate work mode"* / *"Work mode on"* | `work_mode` | Launches **Google Chrome** via CDP (port 9223), opens GitHub, LeetCode, Gmail, and ChatGPT in separate tabs, verifies each tab loaded, and opens **VS Code** in default workspace. |
| *"Open Brave"* / *"Launch Brave"* | `open_brave` | Standalone launcher that opens or focuses **Brave Browser**. |
| *"Open VS Code"* / *"Open Code"* | `open_vscode` | Standalone launcher that opens **Visual Studio Code**. |
| *"Open YouTube"* | `open_youtube_in_brave` | Opens YouTube in Brave browser. |
| *"Search [topic]"* | `youtube_search` | Searches YouTube for the requested topic inside Brave. |
| *"Play 1st video"* / *"Play 2nd video"* | `youtube_play_video` | Clicks and plays the N-th YouTube search result. |
| *"Scroll down"* / *"Scroll up"* | `scroll_page` | Smoothly scrolls active web page. |
| *"Pause video"* / *"Play video"* | `youtube_control` | Toggles YouTube playback. |
| *"Write a simple code of Python in Notepad"* | `open_notepad_and_write_code` | Generates Python code and opens it in Notepad. |
| *"Write a react component in VS Code"* | `open_vscode_and_write_code` | Creates code file in workspace and opens it in VS Code. |
| *"Run code in sandbox"* | `write_and_run_sandbox_code` | Writes code and executes it in Kairos's Monaco sandbox. |

### 🌍 Live World Intelligence (Real-Time, No Hallucination)
| Voice Command (English) | Hinglish Example | Tool Triggered | Action |
|---|---|---|---|
| *"What's today's date?"* / *"What time is it?"* | *"Aaj date kya hai?"* | `get_current_datetime` | Returns real-time date, day of week, and local time. |
| *"Muzaffarnagar news today"* / *"Tech news"* | *"Aaj ki news bata"* | `get_news` | Fetches and reads top 3–5 live headlines from Google News RSS. |
| *"World news"* / *"Top headlines"* | *"Aaj ki world news bata"* | `get_news` | Fetches top global headlines from Google News RSS. |
| *"Who won the match yesterday?"* | *"Kal ka match kisne jeeta?"* | `answer_general_question` | Live web-search backed answer (Tavily → DuckDuckGo fallback). |

---

## 🧪 Running Automated Tests

Kairos includes a complete test suite with **pytest** (284 tests passing) covering gesture control, browser automation, Work Mode CDP integration, security permissions, and the WebSocket voice pipeline.

```bash
cd backend
python -m pytest
```

### Test Suite Matrix

| Test File | What it covers |
|---|---|
| [`test_gesture_control.py`](backend/tests/test_gesture_control.py) | Camera gesture singleton, brightness getter/setter, volume getter/setter, scale clamping, mode switching, status dict structure |
| [`test_work_mode_and_launchers.py`](backend/tests/test_work_mode_and_launchers.py) | Work Mode (Chrome CDP 9223, 4 sites + VS Code), partial failure handling, standalone launchers (`open_brave`, `open_vscode`), missing binary error reporting, port isolation |
| [`test_tool_executor.py`](backend/tests/test_tool_executor.py) | All registered tools with mocked browser/subprocess calls |
| [`test_platform_paths.py`](backend/tests/test_platform_paths.py) | Cross-platform Brave, Chrome, VS Code, and Python path resolvers |
| [`test_browser_suite.py`](backend/tests/test_browser_suite.py) | Browser primitive schemas, ordinal extraction, element resolver |
| [`test_permissions.py`](backend/tests/test_permissions.py) | Allowlist enforcement, path traversal, shell injection, 2-step confirmation |
| [`test_protected_zone.py`](backend/tests/test_protected_zone.py) | System path protection, credential patterns, financial hard-blocks |

---

## 🛡️ License
Built with passion by **Abhishek Kumar** (`@abhishek4524`). All rights reserved.
