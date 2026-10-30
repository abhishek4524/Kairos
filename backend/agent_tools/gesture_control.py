"""
gesture_control.py — Camera Hand Gesture Controller for Kairos.

Features:
  - Access webcam feed (OpenCV + MediaPipe Hands)
  - Right hand: opening finger tips -> increase screen brightness, closing finger tips -> decrease screen brightness
  - Left hand: opening finger tips -> increase volume, closing finger tips -> decrease volume
  - Thread-safe background execution with toggleable preview window
"""

import os
import cv2
import time
import math
import logging
import platform
import threading
import collections
from typing import Dict, Any, Optional, Deque

logger = logging.getLogger("kairos.gesture_control")

# ── PyAutoGUI for Hand Mouse mode ───────────────────────────────────────────
HAS_PYAUTOGUI = False
try:
    import pyautogui
    pyautogui.FAILSAFE = False   # disable corner failsafe for gesture use
    pyautogui.PAUSE = 0          # no delay between commands
    HAS_PYAUTOGUI = True
except Exception as _pag_err:
    logging.getLogger("kairos.gesture_control").warning(f"pyautogui not available: {_pag_err}")

from agent_tools.expression_analyzer import (
    classify_blendshapes,
    ExpressionSmoother,
    draw_cyberpunk_face_hud,
)

# ── Import System Control Libraries ─────────────────────────────────────────
HAS_SBC = False
try:
    import screen_brightness_control as sbc
    HAS_SBC = True
except Exception as e:
    logger.warning(f"screen_brightness_control not available: {e}")

HAS_PYCAW = False
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    import comtypes
    HAS_PYCAW = True
except Exception as e:
    logger.warning(f"pycaw not available: {e}")


# ── System Control Helpers ──────────────────────────────────────────────────

def get_system_brightness() -> int:
    if not HAS_SBC:
        return 50
    try:
        b = sbc.get_brightness()
        if isinstance(b, list):
            return int(b[0]) if b else 50
        return int(b)
    except Exception:
        return 50

def set_system_brightness(val: int) -> int:
    val = max(0, min(100, int(val)))
    if HAS_SBC:
        try:
            sbc.set_brightness(val)
        except Exception as e:
            logger.debug(f"Failed to set brightness via sbc: {e}")
    return val

def _make_volume_interface():
    """Create a fresh COM-initialized pycaw volume interface (call inside the target thread)."""
    if not HAS_PYCAW:
        return None
    try:
        comtypes.CoInitialize()
        speakers = AudioUtilities.GetSpeakers()
        if hasattr(speakers, 'EndpointVolume'):
            return speakers.EndpointVolume
        elif hasattr(speakers, 'Activate'):
            interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return interface.QueryInterface(IAudioEndpointVolume)
    except Exception as e:
        logger.warning(f"Could not create volume interface: {e}")
    return None

def get_system_volume(vol_iface=None) -> int:
    """Get current master volume (0-100). Uses cached interface if provided."""
    if vol_iface is not None:
        try:
            return int(round(vol_iface.GetMasterVolumeLevelScalar() * 100))
        except Exception:
            pass
    if HAS_PYCAW:
        try:
            iface = _make_volume_interface()
            if iface:
                return int(round(iface.GetMasterVolumeLevelScalar() * 100))
        except Exception:
            pass
    return 50

def set_system_volume(val: int, vol_iface=None) -> int:
    """Set master volume (0-100). Uses cached interface if provided."""
    val = max(0, min(100, int(val)))
    success = False
    if vol_iface is not None:
        try:
            vol_iface.SetMasterVolumeLevelScalar(val / 100.0, None)
            success = True
        except Exception as e:
            logger.debug(f"set_system_volume via cache failed: {e}")
    if not success and HAS_PYCAW:
        try:
            iface = _make_volume_interface()
            if iface:
                iface.SetMasterVolumeLevelScalar(val / 100.0, None)
                success = True
        except Exception as e:
            logger.debug(f"Failed to set volume via pycaw: {e}")
            
    if not success:
        try:
            import pyautogui
            curr = get_system_volume()
            diff = val - curr
            if diff > 0:
                for _ in range(max(1, abs(diff) // 4)):
                    pyautogui.press('volumeup')
            elif diff < 0:
                for _ in range(max(1, abs(diff) // 4)):
                    pyautogui.press('volumedown')
        except Exception:
            pass
    return val


# ── Gesture Controller Class ─────────────────────────────────────────────────

class CameraGestureController:
    """
    Background Camera Worker using MediaPipe Hands.
    Modes:
      - 'system'  : Right hand = Brightness, Left hand = Volume
      - 'avatar'  : 3D hologram matrix control
      - 'mouse'   : Full hand mouse — pointer, click, drag, scroll, right-click
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.show_preview = False
        self.camera_id = 0
        self.mode = "system"

        # Live state info
        self.last_brightness = get_system_brightness()
        self.last_volume = get_system_volume()
        self.right_hand_state = "NONE"
        self.left_hand_state = "NONE"
        self.last_error = ""

        # ── Hand Mouse state ─────────────────────────────────────────────────
        self.mouse_action = "IDLE"    # IDLE | MOVING | CLICKING | DRAGGING | SCROLLING | RIGHT_CLICK
        self.mouse_pos = {"x": 0.5, "y": 0.5}   # normalized screen pos

        # ── Facial Expression & Emotion Detection state ──────────────────────
        self.expression_enabled: bool = True  # can be toggled via API
        self.facial_expression: Dict[str, Any] = {
            "emotion": "neutral",
            "confidence": 0.0,
            "label": "Initializing...",
            "description": "no face currently in view",
            "valence": "neutral",
            "arousal": "low",
            "face_detected": False,
            "timestamp": 0.0,
            "metrics": {},
        }
        self._expr_smoother = ExpressionSmoother(window_size=8)

        # Sci-Fi Hologram Telemetry Data
        self.scifi_data = {
            "r_pos": {"x": 0.5, "y": 0.5},
            "l_pos": {"x": 0.5, "y": 0.5},
            "r_pinch": False,
            "l_pinch": False,
            "r_repulsor": False,
            "l_repulsor": False,
            "two_hand_dist": 0.0,
            "r_present": False,
            "l_present": False,
        }

        # MJPEG streaming buffer
        self.latest_frame: Optional[bytes] = None
        self._frame_lock = threading.Lock()

    def set_mode(self, mode: str) -> Dict[str, Any]:
        """Switch mode: 'system', 'avatar', or 'mouse'."""
        mode = mode.lower().strip()
        if mode not in ["system", "avatar", "mouse"]:
            return {"success": False, "error": f"Invalid mode '{mode}'. Choose 'system', 'avatar', or 'mouse'."}
        self.mode = mode
        logger.info(f"[Gesture] Switched gesture mode to '{self.mode}'")
        return {"success": True, "mode": self.mode, "status": self.get_status()}

    def start(self, show_preview: bool = False, camera_id: int = 0, mode: str = "system") -> Dict[str, Any]:
        with self._lock:
            if mode in ["system", "avatar", "mouse"]:
                self.mode = mode
            if self._running:
                return {
                    "success": True,
                    "message": f"Camera gesture control is already running (mode: {self.mode}).",
                    "status": self.get_status()
                }

            self.show_preview = show_preview
            self.camera_id = camera_id
            self._running = True
            self.last_error = ""

            self._thread = threading.Thread(
                target=self._camera_loop,
                daemon=True,
                name="CameraGestureThread"
            )
            self._thread.start()

            return {
                "success": True,
                "message": f"Started camera hand gesture control in '{self.mode}' mode.",
                "status": self.get_status()
            }

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            if not self._running:
                return {"success": True, "message": "Camera gesture control is not running."}
            self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

        return {"success": True, "message": "Stopped camera hand gesture control."}

    def get_facial_expression(self) -> Dict[str, Any]:
        """Returns the latest detected facial expression and emotion analysis."""
        with self._lock:
            return dict(self.facial_expression)

    def toggle_expression(self, enabled: bool) -> Dict[str, Any]:
        """Enable or disable facial expression detection at runtime."""
        self.expression_enabled = enabled
        if not enabled:
            # Clear stale expression data so LLM doesn't keep reacting to it
            with self._lock:
                self.facial_expression = {
                    "emotion": "neutral",
                    "confidence": 0.0,
                    "label": "Expression detection disabled",
                    "description": "facial expression detection is turned off",
                    "valence": "neutral",
                    "arousal": "low",
                    "face_detected": False,
                    "timestamp": 0.0,
                    "metrics": {},
                }
            self._expr_smoother = ExpressionSmoother(window_size=8)
        logger.info(f"[Gesture] Facial expression detection {'enabled' if enabled else 'disabled'}.")
        return {"success": True, "expression_enabled": enabled}

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self._running,
            "mode": self.mode,
            "show_preview": self.show_preview,
            "right_hand": self.right_hand_state,
            "left_hand": self.left_hand_state,
            "brightness": self.last_brightness,
            "volume": self.last_volume,
            "scifi": self.scifi_data,
            "mouse": {"action": self.mouse_action, "pos": self.mouse_pos},
            "expression": self.facial_expression,
            "expression_enabled": self.expression_enabled,
            "last_error": self.last_error
        }

    def _camera_loop(self):
        # ── Use new MediaPipe Tasks API (v1.0+) — optional, graceful fallback ─
        HAS_MEDIAPIPE = False
        mp = None
        mp_python = None
        mp_vision = None
        try:
            import mediapipe as _mp
            from mediapipe.tasks import python as _mp_python
            from mediapipe.tasks.python import vision as _mp_vision
            mp = _mp
            mp_python = _mp_python
            mp_vision = _mp_vision
            HAS_MEDIAPIPE = True
        except ImportError as e:
            warn_msg = f"MediaPipe unavailable ({e}). Streaming camera without hand-gesture detection."
            logger.warning(f"[Gesture] {warn_msg}")
            self.last_error = warn_msg  # informational only, NOT fatal

        # Locate model files (only when MediaPipe loaded successfully)
        detector = None
        face_detector = None
        face_model_path = None
        if HAS_MEDIAPIPE:
            model_path = os.path.join(
                os.path.dirname(__file__), '..', 'tools', 'hand_landmarker.task'
            )
            model_path = os.path.abspath(model_path)
            if not os.path.exists(model_path):
                warn_msg = f"hand_landmarker.task not found at {model_path}. Streaming without gesture detection."
                logger.warning(f"[Gesture] {warn_msg}")
                self.last_error = warn_msg
                HAS_MEDIAPIPE = False

            f_path = os.path.join(
                os.path.dirname(__file__), '..', 'tools', 'face_landmarker.task'
            )
            f_path = os.path.abspath(f_path)
            if os.path.exists(f_path):
                face_model_path = f_path
            else:
                logger.warning(f"[Gesture] face_landmarker.task not found at {f_path}.")

        if HAS_MEDIAPIPE:
            # Build HandLandmarker in VIDEO mode (synchronous per-frame)
            base_options = mp_python.BaseOptions(model_asset_path=model_path)
            options = mp_vision.HandLandmarkerOptions(
                base_options=base_options,
                running_mode=mp_vision.RunningMode.VIDEO,
                num_hands=2,
                min_hand_detection_confidence=0.5,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            try:
                detector = mp_vision.HandLandmarker.create_from_options(options)
            except Exception as e:
                warn_msg = f"HandLandmarker init failed ({e}). Streaming without gesture detection."
                logger.warning(f"[Gesture] {warn_msg}")
                self.last_error = warn_msg
                HAS_MEDIAPIPE = False

            # Build FaceLandmarker with facial blendshapes in VIDEO mode
            if face_model_path:
                try:
                    f_base_opts = mp_python.BaseOptions(model_asset_path=face_model_path)
                    f_options = mp_vision.FaceLandmarkerOptions(
                        base_options=f_base_opts,
                        output_face_blendshapes=True,
                        running_mode=mp_vision.RunningMode.VIDEO,
                        num_faces=1,
                        min_face_detection_confidence=0.45,
                        min_face_presence_confidence=0.45,
                        min_tracking_confidence=0.45,
                    )
                    face_detector = mp_vision.FaceLandmarker.create_from_options(f_options)
                    logger.info("[Gesture] FaceLandmarker initialized with real-time expression detection.")
                except Exception as fe:
                    logger.warning(f"[Gesture] FaceLandmarker init failed ({fe}). Continuing without face expressions.")
                    face_detector = None

        cap = None
        # On Windows, try DirectShow (CAP_DSHOW) first to prevent MSMF resource locks (0xC00D3704)
        if platform.system() == "Windows":
            try:
                c = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
                if c.isOpened():
                    cap = c
            except Exception as _dshow_err:
                logger.warning(f"[Gesture] DirectShow open error: {_dshow_err}")

        if cap is None or not cap.isOpened():
            cap = cv2.VideoCapture(self.camera_id)

        # Fallback to secondary camera indices if primary fails
        if not cap.isOpened():
            for alt_id in [1, 2]:
                if platform.system() == "Windows":
                    try:
                        c = cv2.VideoCapture(alt_id, cv2.CAP_DSHOW)
                        if c.isOpened():
                            cap = c
                            self.camera_id = alt_id
                            break
                    except Exception:
                        pass
                c = cv2.VideoCapture(alt_id)
                if c.isOpened():
                    cap = c
                    self.camera_id = alt_id
                    break

        if cap is None or not cap.isOpened():
            self.last_error = f"Could not open camera index {self.camera_id} or fallback indices"
            self._running = False
            return

        last_r_action_time = time.time()
        last_l_action_time = time.time()
        start_ts = time.time()

        # ── Initialize COM and cache volume interface for this thread ──────────
        vol_iface = _make_volume_interface()
        if vol_iface is not None:
            logger.info("[Gesture] pycaw volume interface cached for gesture thread.")
        else:
            logger.warning("[Gesture] pycaw volume interface unavailable — volume control fallback active.")

        # ── Hand Mouse State (persistent across frames) ───────────────────────
        _scr_w, _scr_h = (1920, 1080)
        if HAS_PYAUTOGUI:
            try:
                _scr_w, _scr_h = pyautogui.size()
            except Exception:
                pass

        # Smoothing: exponential moving average for cursor position
        _smooth_x = _scr_w / 2.0
        _smooth_y = _scr_h / 2.0
        _ALPHA = 0.35           # smoothing factor (lower = smoother but laggier)

        # Control zone: use center 75% of frame as the virtual trackpad
        _CTL_MARGIN = 0.12      # 12% margin on each side

        _pinch_was_active = False
        _drag_active      = False
        _last_click_time  = 0.0
        _last_rclick_time = 0.0
        _last_dclick_time = 0.0
        _scroll_ref_y     = None   # reference y for scroll gesture
        _peace_was_active = False  # two-finger scroll mode

        try:
            while self._running:
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.03)
                    continue

                # Flip frame horizontally — selfie-view
                frame = cv2.flip(frame, 1)
                h, w, _ = frame.shape

                # ── MediaPipe Hand & Face Detection (when available) ─────────
                result = None
                face_result = None
                if HAS_MEDIAPIPE and (detector is not None or face_detector is not None):
                    try:
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        timestamp_ms = int((time.time() - start_ts) * 1000)
                        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

                        if detector is not None:
                            result = detector.detect_for_video(mp_image, timestamp_ms)

                        if face_detector is not None and self.expression_enabled:
                            face_result = face_detector.detect_for_video(mp_image, timestamp_ms)
                    except Exception as _mp_err:
                        logger.debug(f"[Gesture] MediaPipe frame error: {_mp_err}")

                # ── Process Facial Expressions & HUD ────────────────────────
                if self.expression_enabled and face_result and face_result.face_blendshapes and len(face_result.face_blendshapes) > 0:
                    blendshapes = {c.category_name: c.score for c in face_result.face_blendshapes[0]}
                    raw_expr = classify_blendshapes(blendshapes)
                    smoothed_expr = self._expr_smoother.update(raw_expr)
                    with self._lock:
                        self.facial_expression = smoothed_expr

                    if face_result.face_landmarks and len(face_result.face_landmarks) > 0:
                        draw_cyberpunk_face_hud(frame, face_result.face_landmarks[0], smoothed_expr, w, h)
                else:
                    curr_expr = self._expr_smoother.get_current()
                    with self._lock:
                        self.facial_expression = curr_expr

                r_state = "NONE"
                l_state = "NONE"
                r_pos_px = None
                l_pos_px = None

                scifi = {
                    "r_pos": {"x": 0.5, "y": 0.5},
                    "l_pos": {"x": 0.5, "y": 0.5},
                    "r_pinch": False,
                    "l_pinch": False,
                    "r_repulsor": False,
                    "l_repulsor": False,
                    "two_hand_dist": 0.0,
                    "r_present": False,
                    "l_present": False,
                }

                if result is not None and result.hand_landmarks and result.handedness:
                    total_hands_detected = len(result.hand_landmarks)
                    for hand_lm, handedness_list in zip(result.hand_landmarks, result.handedness):
                        raw_label = handedness_list[0].category_name  # "Left" or "Right" as seen by MediaPipe
                        # In mirrored selfie-view (cv2.flip 1), MediaPipe's anatomical classification is inverted:
                        # User's physical Right hand appears as "Left" to MediaPipe, and vice versa.
                        physical_hand = "Right" if raw_label == "Left" else "Left"
                        lm = hand_lm  # list of NormalizedLandmark (.x .y .z)

                        # Palm Center (landmark 9) position
                        palm_x, palm_y = int(lm[9].x * w), int(lm[9].y * h)

                        # ── Draw Sci-Fi Cyberpunk Hand Skeleton Overlay ──────
                        connections = [
                            (0,1),(1,2),(2,3),(3,4),
                            (0,5),(5,6),(6,7),(7,8),
                            (5,9),(9,10),(10,11),(11,12),
                            (9,13),(13,14),(14,15),(15,16),
                            (13,17),(17,18),(18,19),(19,20),(0,17),
                        ]
                        skeleton_color = (255, 230, 0) if physical_hand == "Right" else (255, 100, 0)
                        for a, b in connections:
                            ax, ay = int(lm[a].x * w), int(lm[a].y * h)
                            bx, by = int(lm[b].x * w), int(lm[b].y * h)
                            cv2.line(frame, (ax, ay), (bx, by), skeleton_color, 1, cv2.LINE_AA)

                        # Draw Neon Target Rings on Fingertips [4, 8, 12, 16, 20]
                        for tip_idx in [4, 8, 12, 16, 20]:
                            tx, ty = int(lm[tip_idx].x * w), int(lm[tip_idx].y * h)
                            cv2.circle(frame, (tx, ty), 4, (0, 255, 255), -1, cv2.LINE_AA)
                            cv2.circle(frame, (tx, ty), 8, (255, 0, 255), 1, cv2.LINE_AA)

                        # ── Advanced Sci-Fi Gesture Metrics ───────────────────
                        # Pinch check (Thumb tip 4 vs Index tip 8)
                        pinch_dist = math.hypot(lm[4].x - lm[8].x, lm[4].y - lm[8].y)
                        is_pinched = pinch_dist < 0.065
                        if is_pinched:
                            t4x, t4y = int(lm[4].x * w), int(lm[4].y * h)
                            i8x, i8y = int(lm[8].x * w), int(lm[8].y * h)
                            cv2.line(frame, (t4x, t4y), (i8x, i8y), (255, 0, 255), 2, cv2.LINE_AA)
                            cv2.circle(frame, ((t4x+i8x)//2, (t4y+i8y)//2), 10, (255, 0, 255), 2, cv2.LINE_AA)

                        # Extended fingers check
                        extended_count = 0
                        if lm[8].y < lm[6].y: extended_count += 1
                        if lm[12].y < lm[10].y: extended_count += 1
                        if lm[16].y < lm[14].y: extended_count += 1
                        if lm[20].y < lm[18].y: extended_count += 1
                        thumb_dist = math.hypot(lm[4].x - lm[17].x, lm[4].y - lm[17].y)
                        if thumb_dist > 0.2: extended_count += 1

                        palm_size = max(0.01, math.hypot(lm[9].x - lm[0].x, lm[9].y - lm[0].y))
                        tip_dists = [math.hypot(lm[t].x - lm[0].x, lm[t].y - lm[0].y) for t in [4, 8, 12, 16, 20]]
                        openness_ratio = (sum(tip_dists) / 5.0) / palm_size

                        # Iron Man Repulsor Blast check (all 5 fingers wide open facing forward)
                        is_repulsor = extended_count >= 5 and openness_ratio > 2.3
                        if is_repulsor:
                            # Draw repulsor blast ring around palm
                            cv2.circle(frame, (palm_x, palm_y), 24, (0, 255, 255), 2, cv2.LINE_AA)
                            cv2.circle(frame, (palm_x, palm_y), 36, (0, 200, 255), 1, cv2.LINE_AA)
                            cv2.putText(frame, "REPULSOR BLAST", (palm_x - 45, palm_y - 30),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1, cv2.LINE_AA)

                        # Gesture classification
                        if extended_count >= 4 or openness_ratio > 2.1:
                            gesture = "OPEN"
                        elif extended_count <= 1 or openness_ratio < 1.55:
                            gesture = "CLOSED"
                        else:
                            gesture = "HOLD"

                        now = time.time()
                        if physical_hand == "Right":
                            r_state = gesture
                            r_pos_px = (palm_x, palm_y)
                            scifi["r_present"] = True
                            scifi["r_pos"] = {"x": round(lm[9].x, 3), "y": round(lm[9].y, 3)}
                            scifi["r_pinch"] = is_pinched
                            scifi["r_repulsor"] = is_repulsor

                            if self.mode == "system" and now - last_r_action_time >= 0.08:
                                curr_b = get_system_brightness()
                                if gesture == "OPEN":
                                    set_system_brightness(min(100, curr_b + 4))
                                    self.last_brightness = min(100, curr_b + 4)
                                elif gesture == "CLOSED":
                                    set_system_brightness(max(0, curr_b - 4))
                                    self.last_brightness = max(0, curr_b - 4)
                                last_r_action_time = now

                        elif physical_hand == "Left":
                            l_state = gesture
                            l_pos_px = (palm_x, palm_y)
                            scifi["l_present"] = True
                            scifi["l_pos"] = {"x": round(lm[9].x, 3), "y": round(lm[9].y, 3)}
                            scifi["l_pinch"] = is_pinched
                            scifi["l_repulsor"] = is_repulsor

                            if self.mode == "system" and now - last_l_action_time >= 0.08:
                                curr_v = get_system_volume(vol_iface=vol_iface)
                                if gesture == "OPEN":
                                    new_v = min(100, curr_v + 4)
                                    set_system_volume(new_v, vol_iface=vol_iface)
                                    self.last_volume = new_v
                                elif gesture == "CLOSED":
                                    new_v = max(0, curr_v - 4)
                                    set_system_volume(new_v, vol_iface=vol_iface)
                                    self.last_volume = new_v
                                last_l_action_time = now

                        # ── MOUSE MODE: full hand-mouse control with Right Hand (or single active hand) ──
                        is_mouse_hand = (
                            self.mode == "mouse"
                            and HAS_PYAUTOGUI
                            and (total_hands_detected == 1 or physical_hand == "Right")
                        )
                        if is_mouse_hand:
                            # ── 1. MAP index fingertip to screen (control zone) ─
                            raw_x = lm[8].x  # index tip normalized
                            raw_y = lm[8].y

                            # Remap from control zone to full [0,1]
                            mapped_x = (raw_x - _CTL_MARGIN) / (1 - 2 * _CTL_MARGIN)
                            mapped_y = (raw_y - _CTL_MARGIN) / (1 - 2 * _CTL_MARGIN)
                            mapped_x = max(0.0, min(1.0, mapped_x))
                            mapped_y = max(0.0, min(1.0, mapped_y))

                            # EMA smoothing
                            _smooth_x = _ALPHA * (mapped_x * _scr_w) + (1 - _ALPHA) * _smooth_x
                            _smooth_y = _ALPHA * (mapped_y * _scr_h) + (1 - _ALPHA) * _smooth_y
                            scr_x = int(_smooth_x)
                            scr_y = int(_smooth_y)
                            self.mouse_pos = {"x": round(mapped_x, 3), "y": round(mapped_y, 3)}

                            # ── 2. GESTURE DETECTION ────────────────────────────
                            # Pinch (thumb4 + index8)
                            pinch_dist2 = math.hypot(lm[4].x - lm[8].x, lm[4].y - lm[8].y)
                            is_pinching = pinch_dist2 < 0.06

                            # 3-finger pinch (thumb + index + middle) = right click
                            mid_pinch = math.hypot(lm[4].x - lm[12].x, lm[4].y - lm[12].y)
                            is_3pinch = pinch_dist2 < 0.06 and mid_pinch < 0.07

                            # Peace sign (index + middle up, ring + pinky + thumb down) = scroll
                            idx_up  = lm[8].y < lm[6].y
                            mid_up  = lm[12].y < lm[10].y
                            ring_dn = lm[16].y > lm[14].y
                            pnk_dn  = lm[20].y > lm[18].y
                            is_peace = idx_up and mid_up and ring_dn and pnk_dn and not is_pinching

                            # Fist = all fingers closed → drag mode while moving
                            is_fist = extended_count <= 1

                            mouse_action_this_frame = "MOVING"

                            # ── 3. DRAG (pinch and hold while moving) ───────────
                            if is_pinching and not is_3pinch:
                                if not _pinch_was_active:
                                    # Pinch just started
                                    click_gap = now - _last_click_time
                                    if click_gap < 0.35:
                                        # Double-click!
                                        try: pyautogui.doubleClick(scr_x, scr_y)
                                        except: pass
                                        mouse_action_this_frame = "DOUBLE_CLICK"
                                        _last_dclick_time = now
                                    else:
                                        # Single click start — could become drag
                                        try: pyautogui.mouseDown(scr_x, scr_y)
                                        except: pass
                                        _drag_active = True
                                        _last_click_time = now
                                        mouse_action_this_frame = "CLICKING"
                                    _pinch_was_active = True
                                else:
                                    # Pinch held — dragging
                                    try: pyautogui.moveTo(scr_x, scr_y, duration=0)
                                    except: pass
                                    mouse_action_this_frame = "DRAGGING"
                            else:
                                if _pinch_was_active and _drag_active:
                                    # Pinch released → release mouse button
                                    try: pyautogui.mouseUp()
                                    except: pass
                                    _drag_active = False
                                _pinch_was_active = False

                            # ── 4. RIGHT CLICK (3-finger pinch) ─────────────────
                            if is_3pinch and now - _last_rclick_time > 0.8:
                                try: pyautogui.rightClick(scr_x, scr_y)
                                except: pass
                                _last_rclick_time = now
                                mouse_action_this_frame = "RIGHT_CLICK"

                            # ── 5. SCROLL (peace sign ✌ + move up/down) ──────────
                            elif is_peace:
                                if not _peace_was_active:
                                    _scroll_ref_y = lm[8].y
                                    _peace_was_active = True
                                else:
                                    delta_y = lm[8].y - (_scroll_ref_y or lm[8].y)
                                    scroll_amt = int(delta_y * -18)   # negative = scroll up
                                    if abs(scroll_amt) >= 1:
                                        try: pyautogui.scroll(scroll_amt)
                                        except: pass
                                        _scroll_ref_y = lm[8].y
                                mouse_action_this_frame = "SCROLLING"
                            else:
                                _peace_was_active = False
                                _scroll_ref_y = None

                            # ── 6. FIST GRAB DRAG (closed fist = hold and drag window) ─
                            if is_fist and not is_pinching and not is_peace:
                                try: pyautogui.moveTo(scr_x, scr_y, duration=0)
                                except: pass
                                mouse_action_this_frame = "GRAB_DRAG"

                            # ── 7. Normal cursor move (index up, no pinch) ───────
                            if not is_pinching and not is_peace and not is_fist:
                                try: pyautogui.moveTo(scr_x, scr_y, duration=0)
                                except: pass
                                mouse_action_this_frame = "MOVING"

                            self.mouse_action = mouse_action_this_frame

                            # ── 8. VISUAL HUD for mouse mode ────────────────────
                            tip_x = int(lm[8].x * w)
                            tip_y = int(lm[8].y * h)
                            action_colors = {
                                "MOVING":       (0, 255, 255),
                                "CLICKING":     (0, 255, 0),
                                "DOUBLE_CLICK": (0, 200, 255),
                                "DRAGGING":     (255, 120, 0),
                                "SCROLLING":    (255, 255, 0),
                                "RIGHT_CLICK":  (0, 100, 255),
                                "GRAB_DRAG":    (255, 0, 200),
                            }
                            hud_color = action_colors.get(mouse_action_this_frame, (200, 200, 200))
                            # Pointer ring on index finger tip
                            cv2.circle(frame, (tip_x, tip_y), 12, hud_color, 2, cv2.LINE_AA)
                            cv2.circle(frame, (tip_x, tip_y), 4, hud_color, -1, cv2.LINE_AA)
                            # Cross-hair
                            cv2.line(frame, (tip_x - 18, tip_y), (tip_x + 18, tip_y), hud_color, 1, cv2.LINE_AA)
                            cv2.line(frame, (tip_x, tip_y - 18), (tip_x, tip_y + 18), hud_color, 1, cv2.LINE_AA)
                            # Action label
                            cv2.putText(frame, mouse_action_this_frame, (tip_x + 15, tip_y - 10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, hud_color, 1, cv2.LINE_AA)

                            # Pinch indicator line
                            if is_pinching:
                                t4x, t4y = int(lm[4].x * w), int(lm[4].y * h)
                                cv2.line(frame, (tip_x, tip_y), (t4x, t4y), hud_color, 2, cv2.LINE_AA)
                                cv2.circle(frame, ((tip_x + t4x)//2, (tip_y + t4y)//2), 8, hud_color, 2, cv2.LINE_AA)

                            # Peace/scroll indicator
                            if is_peace:
                                i8x, i8y = int(lm[8].x * w), int(lm[8].y * h)
                                m12x, m12y = int(lm[12].x * w), int(lm[12].y * h)
                                cv2.line(frame, (i8x, i8y), (m12x, m12y), (255, 255, 0), 2, cv2.LINE_AA)
                                cv2.putText(frame, "SCROLL", (i8x - 20, i8y - 20),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1, cv2.LINE_AA)

                # Calculate Two-Hand Laser Beam Distance
                if r_pos_px and l_pos_px:
                    rx, ry = r_pos_px
                    lx, ly = l_pos_px
                    dist_px = math.hypot(rx - lx, ry - ly)
                    norm_dist = round(dist_px / w, 3)
                    scifi["two_hand_dist"] = norm_dist

                    # Draw connecting laser line
                    cv2.line(frame, (rx, ry), (lx, ly), (255, 0, 200), 1, cv2.LINE_AA)
                    mid_x, mid_y = (rx + lx) // 2, (ry + ly) // 2
                    cv2.putText(frame, f"HOLO SPAN: {int(norm_dist * 100)}cm", (mid_x - 45, mid_y - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 100, 255), 1, cv2.LINE_AA)

                self.right_hand_state = r_state
                self.left_hand_state = l_state
                self.scifi_data = scifi

                # ── Sci-Fi Hologram HUD Stream Renderer ───────────────────────
                # Cyberpunk corner brackets ┌ ┐ └ ┘
                c_len = 16
                # Top-Left ┌
                cv2.line(frame, (10, 10), (10 + c_len, 10), (0, 255, 255), 2)
                cv2.line(frame, (10, 10), (10, 10 + c_len), (0, 255, 255), 2)
                # Top-Right ┐
                cv2.line(frame, (w - 10, 10), (w - 10 - c_len, 10), (0, 255, 255), 2)
                cv2.line(frame, (w - 10, 10), (w - 10, 10 + c_len), (0, 255, 255), 2)
                # Bottom-Left └
                cv2.line(frame, (10, h - 10), (10 + c_len, h - 10), (0, 255, 255), 2)
                cv2.line(frame, (10, h - 10), (10, h - 10 - c_len), (0, 255, 255), 2)
                # Bottom-Right ┘
                cv2.line(frame, (w - 10, h - 10), (w - 10 - c_len, h - 10), (0, 255, 255), 2)
                cv2.line(frame, (w - 10, h - 10), (w - 10, h - 10 - c_len), (0, 255, 255), 2)

                # Header & Footer HUD Overlay
                r_color = (0, 255, 0) if r_state == "OPEN" else ((0, 0, 255) if r_state == "CLOSED" else (180, 180, 180))
                l_color = (0, 255, 0) if l_state == "OPEN" else ((0, 0, 255) if l_state == "CLOSED" else (180, 180, 180))
                cv2.rectangle(frame, (0, 0), (w, 42), (15, 15, 15), -1)

                mode_labels = {
                    "system": "SYSTEM CONTROL",
                    "avatar": "HOLO MATRIX 3D",
                    "mouse":  "HAND MOUSE",
                }
                mode_label = mode_labels.get(self.mode, self.mode.upper())
                mp_tag = "" if HAS_MEDIAPIPE else " [NO GESTURE]"
                face_badge = f" | FACE: {self.facial_expression.get('emotion', 'NONE').upper()}" if self.facial_expression.get("face_detected") else ""
                cv2.putText(frame, f"KAIROS NEURAL HUD // {mode_label}{mp_tag}{face_badge}", (12, 18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)

                if self.mode == "system":
                    cv2.putText(frame, f"R(Bright): {self.last_brightness}% [{r_state}]  L(Vol): {self.last_volume}% [{l_state}]",
                                (12, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA)
                elif self.mode == "mouse":
                    action_now = self.mouse_action
                    px = int(self.mouse_pos.get("x", 0.5) * _scr_w)
                    py = int(self.mouse_pos.get("y", 0.5) * _scr_h)
                    cv2.putText(frame,
                                f"ACTION: {action_now} | SCR({px},{py}) | Pinch=Click | ✌=Scroll | 3Pinch=RClick | Fist=Drag",
                                (12, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.33, (0, 255, 200), 1, cv2.LINE_AA)
                else:
                    cv2.putText(frame, f"R:{r_state} L:{l_state} | Pinch=Drag | 2-Hand=Span Scale",
                                (12, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 150, 255), 1, cv2.LINE_AA)

                # Encode frame as JPEG for MJPEG stream endpoint
                ret_enc, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if ret_enc:
                    with self._frame_lock:
                        self.latest_frame = buf.tobytes()

                if self.show_preview:
                    cv2.imshow("Kairos Hand Gesture Control", frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        self._running = False
                        break
                else:
                    time.sleep(0.02)

        except Exception as e:
            logger.error(f"Error in gesture camera loop: {e}")
            self.last_error = str(e)
        finally:
            if detector is not None:
                try:
                    detector.close()
                except Exception:
                    pass
            if face_detector is not None:
                try:
                    face_detector.close()
                except Exception:
                    pass
            if cap is not None:
                cap.release()
            if HAS_PYCAW:
                try:
                    comtypes.CoUninitialize()
                except Exception:
                    pass
            if self.show_preview:
                cv2.destroyAllWindows()
            self._running = False


# Global singleton instance
_controller_instance: Optional[CameraGestureController] = None
_instance_lock = threading.Lock()

def get_gesture_controller() -> CameraGestureController:
    global _controller_instance
    with _instance_lock:
        if _controller_instance is None:
            _controller_instance = CameraGestureController()
        return _controller_instance
