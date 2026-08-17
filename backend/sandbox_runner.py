"""
sandbox_runner.py — Sandboxed code execution engine for Kavya.

Executes user/assistant code in isolated subprocesses with strict execution timeouts,
dedicated temp directories, and output capturing.
"""

import sys
import os
import time
import subprocess
import tempfile
from typing import Dict, Any

SUPPORTED_LANGUAGES = ["python", "javascript", "bash"]

def execute_code(code: str, language: str = "python", timeout_sec: int = 8) -> Dict[str, Any]:
    """
    Executes code in an isolated subprocess.
    Returns:
      {
        "status": "success" | "error" | "timeout",
        "stdout": str,
        "stderr": str,
        "exit_code": int,
        "execution_time_ms": int,
        "language": str
      }
    """
    language = language.lower().strip()
    if language not in SUPPORTED_LANGUAGES:
        return {
            "status": "error",
            "stdout": "",
            "stderr": f"Unsupported language: '{language}'. Supported: {', '.join(SUPPORTED_LANGUAGES)}",
            "exit_code": -1,
            "execution_time_ms": 0,
            "language": language
        }

    # Restrict timeout to 15 seconds max
    timeout_sec = min(15, max(1, timeout_sec))

    with tempfile.TemporaryDirectory(prefix="kavya_sandbox_") as temp_dir:
        # Determine filename and command
        if language == "python":
            script_path = os.path.join(temp_dir, "script.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)
            cmd = [sys.executable, script_path]

        elif language == "javascript":
            script_path = os.path.join(temp_dir, "script.js")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)
            cmd = ["node", script_path]

        elif language == "bash":
            script_path = os.path.join(temp_dir, "script.bat" if sys.platform == "win32" else "script.sh")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)
            cmd = [script_path] if sys.platform == "win32" else ["bash", script_path]

        start_time = time.time()

        try:
            # Clean execution environment (strip secret keys from child env)
            child_env = os.environ.copy()
            for secret in ["GROQ_API_KEY", "NVIDIA_API_KEY", "OPENAI_API_KEY", "ADMIN_PASSWORD", "MONGODB_URI"]:
                child_env.pop(secret, None)

            proc = subprocess.run(
                cmd,
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                env=child_env,
                encoding="utf-8",
                errors="replace"
            )

            execution_time_ms = int((time.time() - start_time) * 1000)
            stdout = proc.stdout[:15000] if proc.stdout else ""
            stderr = proc.stderr[:15000] if proc.stderr else ""

            return {
                "status": "success" if proc.returncode == 0 else "error",
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": proc.returncode,
                "execution_time_ms": execution_time_ms,
                "language": language
            }

        except subprocess.TimeoutExpired:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return {
                "status": "timeout",
                "stdout": "",
                "stderr": f"Execution timed out after {timeout_sec} seconds.",
                "exit_code": -1,
                "execution_time_ms": execution_time_ms,
                "language": language
            }

        except FileNotFoundError as fnf:
            return {
                "status": "error",
                "stdout": "",
                "stderr": f"Runtime interpreter not found: {fnf}. Please ensure {language} is installed on host.",
                "exit_code": -1,
                "execution_time_ms": 0,
                "language": language
            }

        except Exception as ex:
            return {
                "status": "error",
                "stdout": "",
                "stderr": f"Sandbox execution error: {str(ex)}",
                "exit_code": -1,
                "execution_time_ms": 0,
                "language": language
            }
