# Kavya — Desktop App

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.10+ with `backend/venv/` set up
- `backend/venv/Scripts/pip install -r backend/requirements.txt`

### Run in Dev Mode
```powershell
# One-time setup
npm run setup

# Build frontend + launch Electron (dev mode, with DevTools)
npm run electron:dev
```

### Build Windows Installer
```powershell
npm run electron:build-installer
# Output: electron/dist-installer/Kavya Setup 1.0.0.exe
```

---

## Project Structure

```
Personal Assistant/
├── frontend/               React + Vite app (Kavya UI)
│   ├── dist/               Built output loaded by Electron
│   └── components/layout/ElectronTitleBar.jsx  Custom title bar
├── backend/                Python FastAPI backend
│   ├── main.py             WebSocket + REST API
│   ├── llm_agent.py        Kavya LLM persona
│   ├── tts_agent.py        Edge-TTS voice
│   └── venv/               Python virtual env (bundled in installer)
├── electron/               Electron shell
│   ├── main.js             Main process (spawns Python, creates window)
│   ├── preload.js          IPC bridge → window.kavya.*
│   ├── package.json        Electron + electron-builder config
│   └── assets/icon.ico     App icon
├── models/                 faster-whisper model cache
└── package.json            Root convenience scripts
```

---

## IPC API (`window.kavya`)

Available in the renderer via the preload context bridge:

| Method | Description |
|---|---|
| `window.kavya.minimize()` | Minimize window |
| `window.kavya.maximize()` | Toggle maximize/restore |
| `window.kavya.close()` | Close app |
| `window.kavya.isMaximized()` | `Promise<boolean>` |
| `window.kavya.runCommand(cmd, args, opts)` | Run OS command — returns `{code, stdout, stderr}` |
| `window.kavya.openExternal(url)` | Open URL in default browser |
| `window.kavya.showInFolder(path)` | Reveal file in Explorer |
| `window.kavya.backendStatus()` | `{running, port, url}` |
| `window.kavya.platform` | `'electron'` |

---

## Permissions
Mic + audio are granted automatically — no browser permission popup. Configured in `electron/main.js` via `session.setPermissionRequestHandler`.

## Backend Lifecycle
- Spawned as child process on `app.whenReady()`
- Polled at `http://127.0.0.1:8000/` until healthy (up to 30s)
- Killed via `taskkill /T /F` on `app.before-quit`

@abhishek4524
