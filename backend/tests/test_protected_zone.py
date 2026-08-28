"""
test_protected_zone.py — Test suite for permanently off-limits assets,
system paths, credentials, and financial action hard-blocks.
"""

import sys
import os
import unittest

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_tools import protected_zone
from agent_tools import permissions


class TestProtectedZone(unittest.TestCase):

    def test_core_security_files_blocked(self):
        backend_dir = protected_zone.BACKEND_DIR
        sec_files = [
            os.path.join(backend_dir, ".env"),
            os.path.join(backend_dir, "agent_tools", "permissions.py"),
            os.path.join(backend_dir, "agent_tools", "protected_zone.py"),
            os.path.join(backend_dir, "logs", "tool_audit.log"),
        ]
        for sfile in sec_files:
            blocked, reason = protected_zone.is_path_protected(sfile)
            self.assertTrue(blocked, f"Core security file '{sfile}' was not protected!")
            self.assertIn("security", reason.lower() + sfile.lower())

    def test_system_directories_blocked(self):
        sys_paths = [
            r"C:\Windows\System32\cmd.exe",
            r"C:\ProgramData\Microsoft\Crypto",
            "/etc/passwd",
            "/etc/shadow",
            "/usr/bin/sudo",
            "/System/Library/CoreServices",
        ]
        for sp in sys_paths:
            blocked, reason = protected_zone.is_path_protected(sp)
            self.assertTrue(blocked, f"System path '{sp}' was not protected!")

    def test_credential_patterns_blocked(self):
        cred_files = [
            "/home/user/.ssh/id_rsa",
            "C:\\Users\\user\\.ssh\\id_ed25519",
            "private_key.pem",
            "server.key",
            "cert.pfx",
            "Login Data",
            "Cookies",
        ]
        for cf in cred_files:
            blocked, reason = protected_zone.is_path_protected(cf)
            self.assertTrue(blocked, f"Credential file pattern '{cf}' was not protected!")

    def test_financial_actions_hard_blocked(self):
        financial_queries = [
            "Click Pay Now button",
            "confirm purchase for $99",
            "Enter credit card number and cvv",
            "place order and checkout",
            "transfer money to account",
            "complete payment",
        ]
        for query in financial_queries:
            blocked, reason = protected_zone.is_financial_action(query)
            self.assertTrue(blocked, f"Financial query '{query}' was not blocked!")

    def test_full_tool_call_gatekeeper_blocks_protected_zone(self):
        # Attempt to target .env via tool call
        env_path = os.path.join(protected_zone.BACKEND_DIR, ".env")
        res = permissions.validate_tool_call("open_notepad_and_write_code", {
            "filename": env_path,
            "code": "EXPLOIT"
        })
        self.assertFalse(res["permitted"])
        self.assertIn(res["error_type"], ["PROTECTED_ZONE_BLOCKED", "WORKSPACE_VIOLATION"])

        # Attempt financial action via browser tool
        res_fin = permissions.validate_tool_call("find_and_click", {
            "description": "Confirm and Pay Now"
        })
        self.assertFalse(res_fin["permitted"])
        self.assertEqual(res_fin["error_type"], "PROTECTED_ZONE_BLOCKED")
        self.assertTrue(res_fin.get("security_alert"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
