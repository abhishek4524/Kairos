# Kairos Backend Packaging & Bundling Guide

This document outlines the two strategies for packaging the Python FastAPI backend of Kairos for production deployment, along with notes on ML/audio dependencies.

---

## Strategy A: Bundled Virtual Environment (Used by Default)

The default build script in the Electron app (`package.json`) uses `electron-builder`'s `extraResources` configuration to bundle the backend.

### How it Works
1. When you run `npm run build`, `electron-builder` copies the entire `backend/` folder into the packaged resource directory (`resources/backend/`).
2. It excludes heavy ML packages (like `torch` and `nvidia` CUDA libraries) via the `extraResources` filters to keep the installer size reasonable.
3. In production, the Electron main process (`main.js`) resolves the Python executable path to the bundled virtual environment:
   - **Windows**: `resources/backend/venv/Scripts/python.exe`
   - **macOS/Linux**: `resources/backend/venv/bin/python`
4. The main process then spawns `python -m uvicorn main:app` directly from the resources folder.

### Pros & Cons
- **Pros**: 100% reliable python file execution; easy updates; no PyInstaller boot-time overhead.
- **Cons**: Requires the python virtual environment (`venv`) to be prepared on the build machine.

---

## Strategy B: Standalone Packaging via PyInstaller

For environments where distributing a full virtual environment directory is undesirable, you can bundle the backend folder into a single executable using PyInstaller.

### PyInstaller Build Command

Run this command inside the `backend` virtual environment:

```bash
cd backend
venv\Scripts\activate
pip install pyinstaller
pyinstaller --name=kairos-backend --onedir --clean --noconfirm --add-data "venv/Lib/site-packages/faster_whisper;faster_whisper" main.py
```

### Tricky Bundling Issues & Workarounds

ML and desktop automation libraries are notoriously difficult to bundle. Below are the key workarounds for Kairos dependencies:

#### 1. `faster-whisper` (CUDA Libraries)
- **Problem**: CUDA runtime DLLs (like `cublas64_11.dll`, `cudnn_ops_infer64_8.dll`) are loaded dynamically and are often missed by PyInstaller.
- **Solution**: Copy these DLLs from `venv/Lib/site-packages/nvidia/` to the same folder as `kairos-backend.exe`, or configure PyInstaller to include them:
  ```bash
  --collect-all faster_whisper --collect-all nvidia
  ```
- **Alternative**: Fall back to CPU execution if CUDA libraries are missing at runtime.

#### 2. ChromaDB (SQLite & HNSW)
- **Problem**: ChromaDB's vector search index compiles C++ extensions dynamically.
- **Solution**: Force PyInstaller to import ChromaDB's local persistence implementations by adding hidden imports:
  ```bash
  --hidden-import chromadb.segment.impl.vector.local_persistent_hnsw
  ```

#### 3. Playwright (Browser Binaries)
- **Problem**: Playwright browser binaries (Chromium, Firefox, Webkit) are kept in user profile caches (`%USERPROFILE%\AppData\Local\ms-playwright`) rather than python site-packages. They **cannot** be bundled with PyInstaller.
- **Solution**: Keep Playwright as a system-level prerequisite. On first run, the installer or backend must run:
  ```bash
  playwright install chromium
  ```

#### 4. PyAutoGUI / PyDirectInput
- **Problem**: Requires access to display servers or OS API hooks.
- **Solution**: Set `windowsHide: false` or run with elevated user permissions (`asInvoker` or `requireAdministrator`) if automating elevated apps.

#### 5. Local LLM / Ollama
- **Problem**: Embedding a 4GB+ LLM inside a desktop installer is impractical.
- **Solution**: Treat Ollama as an external local service. Use the `keep_alive` setting in Ollama's API payload (e.g. `keep_alive: "5m"`) so that the model automatically unloads from RAM/VRAM after inactivity:
  ```json
  {
    "model": "llama3",
    "prompt": "...",
    "keep_alive": "5m"
  }
  ```
