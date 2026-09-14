"""
build_exe.py — Automated Standalone Packaging Helper Script (Phase G.1)

Executes PyInstaller using pyinstaller_build.spec to package the Kairos FastAPI backend
into a standalone folder/executable.
"""

import os
import sys
import subprocess

def build():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    spec_file = os.path.join(backend_dir, "pyinstaller_build.spec")

    if not os.path.exists(spec_file):
        print(f"[ERROR] Spec file not found at: {spec_file}")
        sys.exit(1)

    print("[BUILD] Packaging Kairos FastAPI Backend into standalone executable...")
    cmd = [sys.executable, "-m", "PyInstaller", spec_file, "--noconfirm"]

    try:
        res = subprocess.run(cmd, cwd=backend_dir, check=True)
        print("[BUILD SUCCESS] Kairos backend successfully packaged into dist/kairos_backend/")
    except subprocess.CalledProcessError as err:
        print(f"[BUILD ERROR] PyInstaller failed with exit code: {err.returncode}")
        sys.exit(err.returncode)

if __name__ == "__main__":
    build()
