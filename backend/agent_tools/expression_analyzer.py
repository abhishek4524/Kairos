"""
expression_analyzer.py — Real-time Facial Expression and Emotion Analysis using MediaPipe Blendshapes.
Maps 52 ARKit facial blendshapes into core emotional states:
- happy (smiling, broad smile, cheerful)
- sad (frowning, downcast, distressed)
- surprised (wide eyes, open jaw, raised brows)
- tired (heavy eyelids, drowsy, yawning)
- angry (furrowed brows, nose sneer, tight lips)
- neutral (calm, resting facial posture)
"""

import collections
import time
from typing import Dict, Any, List, Optional, Tuple
import cv2


def classify_blendshapes(blendshapes: Dict[str, float]) -> Dict[str, Any]:
    """
    Classifies 52 ARKit blendshapes into an emotion dictionary with confidence and metric scores.
    """
    if not blendshapes:
        return {
            "emotion": "neutral",
            "confidence": 0.0,
            "label": "No face detected",
            "description": "no face currently in view",
            "valence": "neutral",
            "arousal": "low",
            "metrics": {},
        }

    # ── Key Blendshape Extractors ─────────────────────────────────────────────
    smile = (blendshapes.get("mouthSmileLeft", 0.0) + blendshapes.get("mouthSmileRight", 0.0)) / 2.0
    cheek_squint = (blendshapes.get("cheekSquintLeft", 0.0) + blendshapes.get("cheekSquintRight", 0.0)) / 2.0
    frown = (blendshapes.get("mouthFrownLeft", 0.0) + blendshapes.get("mouthFrownRight", 0.0)) / 2.0
    brow_down = (blendshapes.get("browDownLeft", 0.0) + blendshapes.get("browDownRight", 0.0)) / 2.0
    brow_inner_up = blendshapes.get("browInnerUp", 0.0)
    brow_outer_up = (blendshapes.get("browOuterUpLeft", 0.0) + blendshapes.get("browOuterUpRight", 0.0)) / 2.0
    jaw_open = blendshapes.get("jawOpen", 0.0)
    eye_wide = (blendshapes.get("eyeWideLeft", 0.0) + blendshapes.get("eyeWideRight", 0.0)) / 2.0
    eye_blink = (blendshapes.get("eyeBlinkLeft", 0.0) + blendshapes.get("eyeBlinkRight", 0.0)) / 2.0
    nose_sneer = (blendshapes.get("noseSneerLeft", 0.0) + blendshapes.get("noseSneerRight", 0.0)) / 2.0
    mouth_press = (blendshapes.get("mouthPressLeft", 0.0) + blendshapes.get("mouthPressRight", 0.0)) / 2.0
    mouth_shrug = (blendshapes.get("mouthShrugLower", 0.0) + blendshapes.get("mouthShrugUpper", 0.0)) / 2.0

    # ── Emotion Composite Scores ──────────────────────────────────────────────
    happy_score = (smile * 0.70) + (cheek_squint * 0.30)
    sad_score = (frown * 0.45) + (brow_inner_up * 0.35) + (mouth_shrug * 0.20)
    surprise_score = (eye_wide * 0.40) + (jaw_open * 0.35) + (brow_outer_up * 0.25)
    angry_score = (brow_down * 0.50) + (nose_sneer * 0.30) + (mouth_press * 0.20)
    tired_score = (eye_blink * 0.65) + (jaw_open * 0.35 if jaw_open > 0.35 else 0.0)

    metrics = {
        "smile": round(smile, 3),
        "frown": round(frown, 3),
        "brow_down": round(brow_down, 3),
        "brow_inner_up": round(brow_inner_up, 3),
        "eye_wide": round(eye_wide, 3),
        "eye_blink": round(eye_blink, 3),
        "jaw_open": round(jaw_open, 3),
    }

    # ── Priority Decision Tree ────────────────────────────────────────────────
    # Happy: clear smiling posture
    if happy_score >= 0.26 and happy_score > (sad_score * 1.2):
        conf = min(0.99, max(0.60, happy_score / 0.65))
        if happy_score > 0.55:
            label = "Very Happy (Broad Smile)"
            desc = "Abhishek is beaming with a broad, joyful smile"
        else:
            label = "Happy (Smiling)"
            desc = "Abhishek has a warm, cheerful smile"
        return {
            "emotion": "happy",
            "confidence": round(conf, 2),
            "label": label,
            "description": desc,
            "valence": "positive",
            "arousal": "high" if happy_score > 0.55 else "medium",
            "metrics": metrics,
        }

    # Surprise: open mouth, wide eyes, raised brows
    if surprise_score >= 0.30 and eye_wide >= 0.28 and happy_score < 0.25:
        conf = min(0.99, max(0.60, surprise_score / 0.60))
        return {
            "emotion": "surprised",
            "confidence": round(conf, 2),
            "label": "Surprised / Shocked",
            "description": "Abhishek looks surprised or amazed with wide eyes and open mouth",
            "valence": "neutral",
            "arousal": "high",
            "metrics": metrics,
        }

    # Sad / Downcast: frown, raised inner brows (grief muscle)
    if sad_score >= 0.20 and happy_score < 0.18:
        conf = min(0.99, max(0.58, sad_score / 0.45))
        return {
            "emotion": "sad",
            "confidence": round(conf, 2),
            "label": "Sad / Downcast",
            "description": "Abhishek looks downcast, sad or distressed",
            "valence": "negative",
            "arousal": "low",
            "metrics": metrics,
        }

    # Angry / Stressed: furrowed brows, nose sneer, pressed lips
    if angry_score >= 0.26 and happy_score < 0.18:
        conf = min(0.99, max(0.58, angry_score / 0.50))
        return {
            "emotion": "angry",
            "confidence": round(conf, 2),
            "label": "Stressed / Angry",
            "description": "Abhishek has a tense, furrowed brow and stressed facial posture",
            "valence": "negative",
            "arousal": "high",
            "metrics": metrics,
        }

    # Tired / Drowsy: heavy eyelids, prolonged half-closed eyes or yawning
    if tired_score >= 0.48 and happy_score < 0.20 and surprise_score < 0.25:
        conf = min(0.99, max(0.55, tired_score / 0.70))
        return {
            "emotion": "tired",
            "confidence": round(conf, 2),
            "label": "Tired / Drowsy",
            "description": "Abhishek looks exhausted, sleepy or heavy-eyed",
            "valence": "neutral",
            "arousal": "low",
            "metrics": metrics,
        }

    # Default: Neutral / Calm
    return {
        "emotion": "neutral",
        "confidence": 0.88,
        "label": "Neutral / Calm",
        "description": "Abhishek has a calm, relaxed and attentive facial expression",
        "valence": "neutral",
        "arousal": "medium",
        "metrics": metrics,
    }


class ExpressionSmoother:
    """
    Temporal smoother over sequential video frames to eliminate single-frame blinks or noise.
    """

    def __init__(self, window_size: int = 8):
        self.window_size = window_size
        self._history: collections.deque = collections.deque(maxlen=window_size)
        self._last_valid_state: Optional[Dict[str, Any]] = None
        self._last_seen_time: float = 0.0

    def update(self, raw_expression: Dict[str, Any]) -> Dict[str, Any]:
        now = time.time()
        self._history.append(raw_expression)
        self._last_seen_time = now

        # Aggregate counts of emotion over the window
        emotion_counts: Dict[str, float] = collections.defaultdict(float)
        total_conf: Dict[str, float] = collections.defaultdict(float)

        for item in self._history:
            emo = item.get("emotion", "neutral")
            conf = item.get("confidence", 0.5)
            # Give higher weight to active emotions (happy, sad, etc.) over neutral to catch genuine smiles quickly
            weight = 1.3 if emo in ("happy", "sad", "surprised", "angry", "tired") else 0.9
            emotion_counts[emo] += weight
            total_conf[emo] += conf

        # Majority vote
        dominant_emo = max(emotion_counts.keys(), key=lambda k: emotion_counts[k])
        avg_conf = total_conf[dominant_emo] / max(1, sum(1 for item in self._history if item.get("emotion") == dominant_emo))

        # Pick the most recent instance of dominant_emo for label & description
        matching_items = [it for it in self._history if it.get("emotion") == dominant_emo]
        representative = matching_items[-1] if matching_items else raw_expression

        smoothed = {
            "emotion": dominant_emo,
            "confidence": round(min(0.99, avg_conf), 2),
            "label": representative.get("label", dominant_emo.title()),
            "description": representative.get("description", ""),
            "valence": representative.get("valence", "neutral"),
            "arousal": representative.get("arousal", "medium"),
            "face_detected": True,
            "timestamp": now,
            "metrics": raw_expression.get("metrics", {}),
        }
        self._last_valid_state = smoothed
        return smoothed

    def get_current(self) -> Dict[str, Any]:
        now = time.time()
        if self._last_valid_state and (now - self._last_seen_time <= 4.0):
            return self._last_valid_state
        return {
            "emotion": "neutral",
            "confidence": 0.0,
            "label": "No face in view",
            "description": "no face currently detected in camera",
            "valence": "neutral",
            "arousal": "low",
            "face_detected": False,
            "timestamp": now,
            "metrics": {},
        }


# Color Palette for Cyberpunk Face Reticle based on emotion (BGR)
EMOTION_COLORS = {
    "happy": (50, 255, 120),       # Neon green / emerald
    "sad": (255, 120, 90),         # Gentle indigo / cornflower blue
    "surprised": (0, 230, 255),    # Vivid electric amber
    "angry": (60, 60, 255),        # Crimson red
    "tired": (0, 160, 255),        # Deep warm orange
    "neutral": (255, 220, 0),      # Neon cyan / teal
}


def draw_cyberpunk_face_hud(
    frame,
    face_landmarks,
    expression_info: Dict[str, Any],
    w: int,
    h: int
):
    """
    Renders high-tech Cyberpunk Face Reticle and Expression Telemetry on the video frame.
    """
    if not face_landmarks:
        return

    # Extract 2D pixel coordinates of all face landmarks
    xs = [int(lm.x * w) for lm in face_landmarks]
    ys = [int(lm.y * h) for lm in face_landmarks]

    min_x, max_x = max(0, min(xs)), min(w - 1, max(xs))
    min_y, max_y = max(0, min(ys)), min(h - 1, max(ys))

    # Add 12% padding around the face
    pad_x = int((max_x - min_x) * 0.12)
    pad_y = int((max_y - min_y) * 0.12)
    x1, y1 = max(4, min_x - pad_x), max(4, min_y - pad_y)
    x2, y2 = min(w - 5, max_x + pad_x), min(h - 5, max_y + pad_y)

    emo = expression_info.get("emotion", "neutral")
    conf = int(expression_info.get("confidence", 0.85) * 100)
    color = EMOTION_COLORS.get(emo, (255, 220, 0))

    # ── Corner Reticles ───────────────────────────────────────────────────────
    c_len = max(14, int((x2 - x1) * 0.15))
    # Top-Left ┌
    cv2.line(frame, (x1, y1), (x1 + c_len, y1), color, 2, cv2.LINE_AA)
    cv2.line(frame, (x1, y1), (x1, y1 + c_len), color, 2, cv2.LINE_AA)
    # Top-Right ┐
    cv2.line(frame, (x2, y1), (x2 - c_len, y1), color, 2, cv2.LINE_AA)
    cv2.line(frame, (x2, y1), (x2, y1 + c_len), color, 2, cv2.LINE_AA)
    # Bottom-Left └
    cv2.line(frame, (x1, y2), (x1 + c_len, y2), color, 2, cv2.LINE_AA)
    cv2.line(frame, (x1, y2), (x1, y2 - c_len), color, 2, cv2.LINE_AA)
    # Bottom-Right ┘
    cv2.line(frame, (x2, y2), (x2 - c_len, y2), color, 2, cv2.LINE_AA)
    cv2.line(frame, (x2, y2), (x2, y2 - c_len), color, 2, cv2.LINE_AA)

    # ── Face HUD Header Tag ───────────────────────────────────────────────────
    tag_text = f"NEURAL SCAN // {emo.upper()} {conf}%"
    (tw, th), _ = cv2.getTextSize(tag_text, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
    tag_y = max(18, y1 - 8)
    cv2.rectangle(frame, (x1, tag_y - th - 4), (x1 + tw + 10, tag_y + 4), (10, 10, 10), -1)
    cv2.putText(frame, tag_text, (x1 + 5, tag_y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)

    # ── Key Facial Landmark Accent Dots (Lips & Eyes) ─────────────────────────
    # Lips center: 13, 14, 61, 291. Eyes: 33, 263.
    for p_idx in [13, 61, 291, 33, 263]:
        if p_idx < len(face_landmarks):
            px = int(face_landmarks[p_idx].x * w)
            py = int(face_landmarks[p_idx].y * h)
            cv2.circle(frame, (px, py), 2, color, -1, cv2.LINE_AA)
