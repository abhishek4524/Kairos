"""
test_permissions.py — Test suite for permission allowlist, workspace containment,
command sanitization, and two-step confirmation flows.
"""

import sys
import os
import unittest
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_tools import permissions
from agent_tools.executor import execute_tool, confirm_pending_action


class TestPermissionsEngine(unittest.TestCase):

    def setUp(self):
        permissions.ensure_workspace_dirs()

    def test_allowed_tool_passes(self):
        res = permissions.validate_tool_call("navigate_to", {"url_or_search_query": "https://wikipedia.org"})
        self.assertTrue(res["permitted"])

    def test_disallowed_tool_blocked(self):
        res = permissions.validate_tool_call("malicious_unauthorized_tool", {})
        self.assertFalse(res["permitted"])
        self.assertEqual(res["error_type"], "PERMISSION_DENIED")

    def test_path_traversal_blocked(self):
        # Attempt to write outside workspace directory
        res = permissions.validate_tool_call("open_notepad_and_write_code", {
            "filename": "../../Windows/System32/evil.bat",
            "code": "echo evil"
        })
        self.assertFalse(res["permitted"])
        self.assertEqual(res["error_type"], "WORKSPACE_VIOLATION")

    def test_shell_injection_sanitization_strict_mode(self):
        res = permissions.validate_tool_call("write_and_run_sandbox_code", {
            "language": "bash",
            "code": "echo hello; rm -rf /"
        })
        self.assertFalse(res["permitted"])
        self.assertEqual(res["error_type"], "SHELL_INJECTION_DETECTED")

    def test_destructive_action_two_step_confirmation_flow(self):
        # 1. Initiating delete_file should require confirmation
        guard = permissions.validate_tool_call("delete_file", {"filename": "old_draft.txt"})
        self.assertFalse(guard["permitted"])
        self.assertTrue(guard["requires_confirmation"])
        self.assertEqual(guard["confirmation_type"], "DESTRUCTIVE")
        action_id = guard["action_id"]
        self.assertIsNotNone(action_id)

        # 2. Ambiguous confirmation should decline
        ok, pending, reason = permissions.confirmation_mgr.validate_confirmation(action_id, "maybe later")
        self.assertFalse(ok)
        self.assertIn("Ambiguous reply", reason)

        # 3. Register a new action and confirm explicitly
        guard2 = permissions.validate_tool_call("delete_file", {"filename": "old_draft.txt"})
        action_id2 = guard2["action_id"]
        ok2, pending2, reason2 = permissions.confirmation_mgr.validate_confirmation(action_id2, "yes confirm")
        self.assertTrue(ok2)
        self.assertEqual(pending2.tool_name, "delete_file")

    def test_communication_two_step_confirmation_flow(self):
        # Missing/ambiguous recipient should fail disambiguation
        guard_bad = permissions.validate_tool_call("send_whatsapp_message", {
            "recipient": "",
            "message": "Hello"
        })
        self.assertFalse(guard_bad["permitted"])
        self.assertEqual(guard_bad["error_type"], "AMBIGUOUS_RECIPIENT")

        # Valid communication requires confirmation
        guard = permissions.validate_tool_call("send_whatsapp_message", {
            "recipient": "+919876543210",
            "message": "Meeting is at 5 PM"
        })
        self.assertFalse(guard["permitted"])
        self.assertTrue(guard["requires_confirmation"])
        self.assertEqual(guard["confirmation_type"], "COMMUNICATION")
        action_id = guard["action_id"]

        # Confirm communication
        ok, pending, reason = permissions.confirmation_mgr.validate_confirmation(action_id, "send it")
        self.assertTrue(ok)
        self.assertEqual(pending.params["recipient"], "+919876543210")

    def test_trash_recovery_mechanism(self):
        # Create a test file in workspace
        test_file = os.path.join(permissions.DEFAULT_WORKSPACE, "test_trash_file.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Sample test content for trash recovery")
        
        self.assertTrue(os.path.exists(test_file))
        ok, msg = permissions.move_to_trash(test_file)
        self.assertTrue(ok)
        self.assertFalse(os.path.exists(test_file))
        self.assertIn("safely moved to trash", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
