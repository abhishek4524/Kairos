"""
test_gesture_control.py — Unit tests for Camera Gesture Control feature.
"""

import unittest
from unittest.mock import patch, MagicMock
from agent_tools import gesture_control


class TestGestureControl(unittest.TestCase):

    def test_get_system_brightness(self):
        b = gesture_control.get_system_brightness()
        self.assertIsInstance(b, int)
        self.assertGreaterEqual(b, 0)
        self.assertLessEqual(b, 100)

    def test_get_system_volume(self):
        v = gesture_control.get_system_volume()
        self.assertIsInstance(v, int)
        self.assertGreaterEqual(v, 0)
        self.assertLessEqual(v, 100)

    def test_set_brightness_clamp(self):
        v1 = gesture_control.set_system_brightness(150)
        self.assertEqual(v1, 100)
        v2 = gesture_control.set_system_brightness(-20)
        self.assertEqual(v2, 0)

    def test_set_volume_clamp(self):
        v1 = gesture_control.set_system_volume(150)
        self.assertEqual(v1, 100)
        v2 = gesture_control.set_system_volume(-20)
        self.assertEqual(v2, 0)

    def test_controller_singleton_and_status(self):
        gc = gesture_control.get_gesture_controller()
        status = gc.get_status()
        self.assertIn("is_running", status)
        self.assertIn("brightness", status)
        self.assertIn("volume", status)
        self.assertIn("right_hand", status)
        self.assertIn("left_hand", status)
        self.assertIn("expression", status)

    def test_facial_expression_status_and_getter(self):
        gc = gesture_control.get_gesture_controller()
        expr = gc.get_facial_expression()
        self.assertIsInstance(expr, dict)
        self.assertIn("emotion", expr)
        self.assertIn("confidence", expr)
        status = gc.get_status()
        self.assertIn("expression", status)


if __name__ == "__main__":
    unittest.main()
