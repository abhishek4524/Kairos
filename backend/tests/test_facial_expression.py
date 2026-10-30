"""
test_facial_expression.py — Unit tests for Real-Time Facial Expression Detection & Arya Visual Perception.
"""

import time
import unittest
from unittest.mock import patch, MagicMock

from agent_tools.expression_analyzer import (
    classify_blendshapes,
    ExpressionSmoother,
)
from agent_tools.gesture_control import get_gesture_controller
from agent_tools.executor import execute_tool


class TestFacialExpressionDetection(unittest.TestCase):

    def test_classify_happy_smile(self):
        blendshapes = {
            "mouthSmileLeft": 0.65,
            "mouthSmileRight": 0.70,
            "cheekSquintLeft": 0.45,
            "cheekSquintRight": 0.50,
        }
        res = classify_blendshapes(blendshapes)
        self.assertEqual(res["emotion"], "happy")
        self.assertGreaterEqual(res["confidence"], 0.60)
        self.assertEqual(res["valence"], "positive")
        self.assertIn("smile", res["metrics"])

    def test_classify_sad_frown(self):
        blendshapes = {
            "mouthFrownLeft": 0.55,
            "mouthFrownRight": 0.50,
            "browInnerUp": 0.45,
            "mouthShrugLower": 0.30,
        }
        res = classify_blendshapes(blendshapes)
        self.assertEqual(res["emotion"], "sad")
        self.assertGreaterEqual(res["confidence"], 0.55)
        self.assertEqual(res["valence"], "negative")

    def test_classify_surprised(self):
        blendshapes = {
            "eyeWideLeft": 0.55,
            "eyeWideRight": 0.60,
            "jawOpen": 0.50,
            "browOuterUpLeft": 0.40,
        }
        res = classify_blendshapes(blendshapes)
        self.assertEqual(res["emotion"], "surprised")
        self.assertGreaterEqual(res["confidence"], 0.60)

    def test_classify_angry_stressed(self):
        blendshapes = {
            "browDownLeft": 0.60,
            "browDownRight": 0.55,
            "noseSneerLeft": 0.35,
            "mouthPressLeft": 0.30,
        }
        res = classify_blendshapes(blendshapes)
        self.assertEqual(res["emotion"], "angry")
        self.assertGreaterEqual(res["confidence"], 0.55)
        self.assertEqual(res["valence"], "negative")

    def test_classify_tired(self):
        blendshapes = {
            "eyeBlinkLeft": 0.75,
            "eyeBlinkRight": 0.70,
            "jawOpen": 0.40,
        }
        res = classify_blendshapes(blendshapes)
        self.assertEqual(res["emotion"], "tired")
        self.assertGreaterEqual(res["confidence"], 0.55)

    def test_classify_neutral_resting(self):
        blendshapes = {
            "mouthSmileLeft": 0.05,
            "mouthFrownLeft": 0.02,
            "browDownLeft": 0.03,
            "eyeWideLeft": 0.04,
        }
        res = classify_blendshapes(blendshapes)
        self.assertEqual(res["emotion"], "neutral")
        self.assertEqual(res["label"], "Neutral / Calm")

    def test_expression_smoother(self):
        smoother = ExpressionSmoother(window_size=5)
        raw_happy = classify_blendshapes({"mouthSmileLeft": 0.8, "mouthSmileRight": 0.8})

        for _ in range(4):
            smoothed = smoother.update(raw_happy)

        self.assertEqual(smoothed["emotion"], "happy")
        self.assertTrue(smoothed["face_detected"])

        curr = smoother.get_current()
        self.assertEqual(curr["emotion"], "happy")
        self.assertTrue(curr["face_detected"])

    def test_gesture_controller_expression_integration(self):
        gc = get_gesture_controller()
        expr = gc.get_facial_expression()
        self.assertIsInstance(expr, dict)
        self.assertIn("emotion", expr)
        self.assertIn("confidence", expr)
        self.assertIn("face_detected", expr)

        status = gc.get_status()
        self.assertIn("expression", status)

    def test_executor_get_facial_expression_tool(self):
        res = execute_tool("get_facial_expression", {})
        self.assertTrue(res.get("success"))
        self.assertIn("expression", res)
        self.assertIn("emotion", res["expression"])


if __name__ == "__main__":
    unittest.main()
