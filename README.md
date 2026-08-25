# Kairos — Autonomous Desktop AI Assistant & Living Neural Core

<div align="center">

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![React](https://img.shields.io/badge/React_18-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Three.js](https://img.shields.io/badge/Three.js-000000?style=for-the-badge&logo=three.js&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_Memory-orange?style=for-the-badge)

**A high-performance, real-time voice-interactive personal AI assistant powered by a 3D Living Neural Core, long-term vector memory, and autonomous desktop tool execution.**

</div>

---

## 🌟 Key Highlights

### 🧠 1. 3D Living Neural Core Centerpiece
- **Real-Time State Machine (11 States):** Visually reflects every cognitive phase — `IDLE`, `LISTENING`, `PROCESSING_INPUT`, `THINKING`, `GENERATING`, `MEMORY_UPDATE`, `RAG_INGESTION`, `RAG_RETRIEVAL`, `TOOL_EXECUTION`, `SUCCESS`, and `ERROR`.
- **Refined Geodesic Geometry:** Clean wireframe icosahedron nucleus with counter-rotating octahedron inner shell, instanced synaptic nodes, and directional signal particle flows.
- **Audio-Reactive Synced Pulses:** 3D core breathing, dynamic scaling, and particle radiation dynamically driven by live `AnalyserNode` audio waveforms throughout the **entire duration of speech**.
- **Fluid 3D Mouse Controls:** Smooth OrbitControls with damping, mouse wheel zoom (`1.0x`–`25.0x`), right-click pan, quick on-screen zoom toolbar (`[+]`, `[-]`, `[↺ Reset]`), and perspective presets (`GALAXY`, `CORE`, `MEMORY`).

### 🎙️ 2. Real-Time Streaming Voice Engine
- **Ultra-Low Latency WebSocket Pipeline:** Full-duplex audio chunk streaming between React frontend and FastAPI backend.
- **Local STT (Faster-Whisper):** Real-time speech-to-text with Voice Activity Detection (Silero VAD / Energy RMS fallback).
- **Male Neural TTS:** Edge-TTS powered voice synthesis featuring `en-US-ChristopherNeural` (crisp, authoritative, intelligent AI voice) and `hi-IN-MadhurNeural` for Hindi.
- **Continuous Listening Mode:** Hands-free voice conversation with automated turn resumption.

### 📚 3. Long-Term Vector Memory & Document RAG
- **Episodic Fact Extraction:** Automatically extracts and remembers user preferences, goals, and facts across conversations.
- **ChromaDB Knowledge Retrieval:** Ingest PDFs, markdown notes, and text files into vector storage with semantic chunk search during queries.
- **Memory Management Panel:** Pin critical facts to always inject into context, inspect chunk similarity scores, or delete items on demand.

### 💻 4. Desktop Agentic Capabilities & Code Sandbox
- **Built-in Code Sandbox:** Interactive Monaco editor with Python 3 and Node.js execution sandbox.
- **Native OS Execution:** Controlled desktop command execution via Electron context bridge (`window.kavya.*`).
- **Security Confirmation Layer:** Interactive UI approval chips before executing sensitive OS actions.

### 🌑 5. Pure Dark Obsidian Aesthetic
- **100% Dark Mode (`#02040a`):** Sleek, distraction-free sci-fi interface with glassmorphism, steel-blue accents, live equalizer wave, and model parameter telemetry HUD.

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
│   ├── tts_agent.py              # Male Neural Edge-TTS engine
│   ├── db.py                     # SQLite / MongoDB conversation persistence
│   ├── chroma_db/                # ChromaDB vector store & embeddings
│   └── agent_tools/              # Desktop automation tool registry
├── electron/                     # Electron Desktop Wrapper
│   ├── main.js                   # Main process, Python process supervisor
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

### 1. Installation
```powershell
# Clone the repository
git clone https://github.com/abhishek4524/Kavya.git
cd "Personal Assistant"

# Install root dependencies
npm run setup

# Install Python backend dependencies
cd backend
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
cd ..
```

### 2. Environment Configuration
Create a `.env` file in `backend/`:
```env
GROQ_API_KEY=your_groq_api_key_here
NVIDIA_API_KEY=optional_nvidia_nim_fallback_key
PORT=8000
```

### 3. Run in Development Mode
```powershell
# Option A: Run Electron Desktop App (spawns Python backend automatically)
npm run electron:dev

# Option B: Run Browser Web View
# Terminal 1 (Backend):
cd backend
.\venv\Scripts\uvicorn main:app --reload --port 8000

# Terminal 2 (Frontend):
cd frontend
npm run dev
# Open http://localhost:5173
```

### 4. Build Production Windows Installer
```powershell
npm run electron:build-installer
# Generates installer in electron/dist-installer/
```

---

## 🔌 Electron IPC Context Bridge (`window.kavya`)

The frontend interacts with native OS capabilities through a secure context bridge in `electron/preload.js`:

| Method | Returns | Description |
|---|---|---|
| `window.kavya.minimize()` | `void` | Minimizes application window |
| `window.kavya.maximize()` | `void` | Toggles maximize / restore window |
| `window.kavya.close()` | `void` | Gracefully closes application and terminates backend |
| `window.kavya.isMaximized()` | `Promise<boolean>` | Checks current window state |
| `window.kavya.runCommand(cmd, args, opts)` | `Promise<{code, stdout, stderr}>` | Runs sandboxed command on local system |
| `window.kavya.openExternal(url)` | `void` | Opens link in default browser |
| `window.kavya.showInFolder(path)` | `void` | Reveals file or directory in Windows Explorer |
| `window.kavya.backendStatus()` | `Promise<{running, port, url}>` | Checks Python backend health status |

---

## 🤖 Kairos AI Persona & System Instructions
- **Name:** Kairos
- **Personality:** Warm, friendly, highly intelligent, and loyal personal assistant.
- **Language Policy:** Understands multilingual queries (English, Hindi, Hinglish); responds in **100% natural, clear English voice and text**.
- **Spoken Greeting:** *"Hi! I'm Kairos, your friendly AI assistant. How can I help you today?"*

---

## 🛡️ License
Built by **Abhishek Kumar** (`@abhishek4524`). All rights reserved.
