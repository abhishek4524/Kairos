# -*- mode: python ; coding: utf-8 -*-
"""
pyinstaller_build.spec — Standalone Executable Spec for Kairos FastAPI Backend (Phase G.1)

Builds a self-contained executable for the Kairos backend including:
- FastAPI / Uvicorn server runtime
- Multi-provider AI router & local Ollama abstraction
- Offline Piper TTS binaries & ONNX voice models
- Risk-based Security Gatekeeper & Task Planner
"""

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Base directory
backend_dir = os.path.dirname(os.path.abspath(SPEC))

# Data files to bundle (piper models, static assets, schemas)
datas = [
    (os.path.join(backend_dir, 'models'), 'models'),
]

# Hidden imports required by dynamic dispatchers & sub-agents
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'engineio.async_drivers.asgi',
    'providers.base_provider',
    'providers.groq_provider',
    'providers.nvidia_provider',
    'providers.ollama_provider',
    'providers.piper_tts',
    'core.connectivity',
    'core.task_planner',
    'agent_tools.dev_tools',
    'agent_tools.permissions',
    'agent_tools.executor',
    'agents.dev_agent',
    'agents.orchestrator',
]

a = Analysis(
    ['main.py'],
    pathex=[backend_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='kairos_backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True, # Set to False for production background execution
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='kairos_backend',
)
