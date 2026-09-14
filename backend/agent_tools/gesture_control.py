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
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger("kairos.gesture_control")

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
    Background Camera Worker that uses MediaPipe Hands to control
    Brightness (Right Hand) and Volume (Left Hand).
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.show_preview = False
        self.camera_id = 0
        self.mode = "system"   # "system" (Brightness/Volume) or "avatar" (3D Model)
        
        # Live state info
        self.last_brightness = get_system_brightness()
        self.last_volume = get_system_volume()
        self.right_hand_state = "NONE"   # "OPEN", "CLOSED", "HOLD", "NONE"
        self.left_hand_state = "NONE"    # "OPEN", "CLOSED", "HOLD", "NONE"
        self.last_error = ""

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

        # MJPEG streaming buffer — latest encoded JPEG frame bytes
        self.latest_frame: Optional[bytes] = None
        self._frame_lock = threading.Lock()

    def set_mode(self, mode: str) -> Dict[str, Any]:
        """Switch mode between 'system' (Brightness/Volume) and 'avatar' (3D Model Control)."""
        mode = mode.lower().strip()
        if mode not in ["system", "avatar"]:
            return {"success": False, "error": f"Invalid mode '{mode}'. Choose 'system' or 'avatar'."}
        self.mode = mode
        logger.info(f"[Gesture] Switched gesture mode to '{self.mode}'")
        return {"success": True, "mode": self.mode, "status": self.get_status()}

    def start(self, show_preview: bool = False, camera_id: int = 0, mode: str = "system") -> Dict[str, Any]:
        with self._lock:
            if mode in ["system", "avatar"]:
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
            "last_error": self.last_error
        }

    def _camera_loop(self):
        # ── Use new MediaPipe Tasks API (v1.0+) ──────────────────────────────
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision
        except ImportError as e:
            self.last_error = f"MediaPipe import failed: {e}"
            self._running = False
            return

        # Locate model file
        model_path = os.path.join(
            os.path.dirname(__file__), '..', 'tools', 'hand_landmarker.task'
        )
        model_path = os.path.abspath(model_path)
        if not os.path.exists(model_path):
            self.last_error = f"hand_landmarker.task model not found at {model_path}"
            self._running = False
            return

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

        cap = cv2.VideoCapture(self.camera_id)
        if not cap.isOpened():
            self.last_error = f"Could not open camera index {self.camera_id}"
            self._running = False
            return

        detector = mp_vision.HandLandmarker.create_from_options(options)
        last_r_action_time = time.time()
        last_l_action_time = time.time()
        start_ts = time.time()

        # ── Initialize COM and cache volume interface for this thread ──────────
        vol_iface = _make_volume_interface()
        if vol_iface is not None:
            logger.info("[Gesture] pycaw volume interface cached for gesture thread.")
        else:
            logger.warning("[Gesture] pycaw volume interface unavailable — volume control fallback active.")

        try:
            while self._running:
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.03)
                    continue

                # Flip frame horizontally — selfie-view
                frame = cv2.flip(frame, 1)
                h, w, _ = frame.shape

                # Convert to RGB for MediaPipe
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                timestamp_ms = int((time.time() - start_ts) * 1000)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                result = detector.detect_for_video(mp_image, timestamp_ms)

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

                if result.hand_landmarks and result.handedness:
                    for hand_lm, handedness_list in zip(result.hand_landmarks, result.handedness):
                        hand_label = handedness_list[0].category_name  # "Left" or "Right"
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
                        skeleton_color = (255, 230, 0) if hand_label == "Right" else (255, 100, 0)
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
                        if hand_label == "Right":
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

                        elif hand_label == "Left":
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
                
                mode_label = "SYSTEM CONTROL" if self.mode == "system" else "HOLO MATRIX 3D"
                cv2.putText(frame, f"KAIROS NEURAL HUD // {mode_label}", (12, 18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)

                if self.mode == "system":
                    cv2.putText(frame, f"R(Bright): {self.last_brightness}% [{r_state}]  L(Vol): {self.last_volume}% [{l_state}]",
                                (12, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA)
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
            detector.close()
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
