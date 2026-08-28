"""
test_platform_paths.py — Test suite for cross-platform executable & path resolvers.
"""

import sys
import os
import unittest
import platform

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import platform_paths


class TestPlatformPaths(unittest.TestCase):

    def test_os_detection(self):
        current = platform.system()
        self.assertEqual(platform_paths.SYSTEM, current)
        if current == "Windows":
            self.assertTrue(platform_paths.IS_WINDOWS)
            self.assertFalse(platform_paths.IS_MACOS)
            self.assertFalse(platform_paths.IS_LINUX)
        elif current == "Darwin":
            self.assertTrue(platform_paths.IS_MACOS)
            self.assertFalse(platform_paths.IS_WINDOWS)
        elif current == "Linux":
            self.assertTrue(platform_paths.IS_LINUX)
            self.assertFalse(platform_paths.IS_WINDOWS)

    def test_env_overrides(self):
        # Test KAIROS_BRAVE_PATH override
        os.environ["KAIROS_BRAVE_PATH"] = sys.executable
        brave = platform_paths.get_brave_path()
        self.assertEqual(brave, sys.executable)
        del os.environ["KAIROS_BRAVE_PATH"]

        # Test KAIROS_VSCODE_PATH override
        os.environ["KAIROS_VSCODE_PATH"] = "custom_code_path"
        vscode = platform_paths.get_vscode_path()
        self.assertEqual(vscode, "custom_code_path")
        del os.environ["KAIROS_VSCODE_PATH"]

        # Test KAIROS_PYTHON_PATH override
        os.environ["KAIROS_PYTHON_PATH"] = sys.executable
        py = platform_paths.get_venv_python_path()
        self.assertEqual(py, sys.executable)
        del os.environ["KAIROS_PYTHON_PATH"]

    def test_text_editor_command(self):
        cmd = platform_paths.get_text_editor_command("test.txt")
        self.assertIsInstance(cmd, list)
        self.assertIn("test.txt", cmd)

    def test_diagnostics(self):
        results = platform_paths.check_required_executables()
        self.assertIn("brave", results)
        self.assertIn("vscode", results)
        self.assertIn("python", results)
        self.assertTrue(results["python"]["found"])
        self.assertIn("KAIROS_BRAVE_PATH", results["brave"]["help"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
