"""
connectivity.py — Connectivity Manager & State Machine for Kairos.

States:
  ONLINE      — Primary cloud providers operational (Groq / NVIDIA NIM).
  DEGRADED    — Elevated latency or initial cloud errors; retries in progress.
  OFFLINE     — Cloud unreachable; routing strictly to local Ollama.
  RECOVERING  — Internet re-detected; performing verification health check against Groq.

Transition Rules:
  ONLINE      → DEGRADED    (Cloud latency high / API failure)
  DEGRADED    → OFFLINE     (Unreachable after retry window)
  DEGRADED    → ONLINE      (Health check passes again)
  OFFLINE     → RECOVERING  (Background network probe succeeds)
  RECOVERING  → ONLINE      (Real Groq health check passes)
  RECOVERING  → OFFLINE     (Health check fails on flicker)
"""

import asyncio
import enum
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import psutil
from agent_tools import audit_logger
from providers.groq_provider import GroqProvider
from providers.ollama_provider import OllamaProvider

logger = logging.getLogger("kairos.connectivity")

HEALTH_INTERVAL_SECONDS = float(os.getenv("KAIROS_NETWORK_HEALTH_INTERVAL_SECONDS", "10.0"))
AUTO_FALLBACK_TO_OLLAMA = os.getenv("KAIROS_AUTO_FALLBACK_TO_OLLAMA", "1").lower() in ("1", "true", "yes")
AUTO_RECOVER_TO_CLOUD = os.getenv("KAIROS_AUTO_RECOVER_TO_CLOUD", "1").lower() in ("1", "true", "yes")

GOLDEN_RULE_FALLBACK_MESSAGE = (
    "Internet unavailable hai. Local AI abhi installed nahi hai, lekin main apps control kar sakta hoon, "
    "saved documents search kar sakta hoon, files manage kar sakta hoon."
)


class ConnectivityState(str, enum.Enum):
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    RECOVERING = "RECOVERING"


VALID_TRANSITIONS: Dict[ConnectivityState, Set[ConnectivityState]] = {
    ConnectivityState.ONLINE: {ConnectivityState.DEGRADED},
    ConnectivityState.DEGRADED: {ConnectivityState.OFFLINE, ConnectivityState.ONLINE},
    ConnectivityState.OFFLINE: {ConnectivityState.RECOVERING},
    ConnectivityState.RECOVERING: {ConnectivityState.ONLINE, ConnectivityState.OFFLINE},
}


class ConnectivityManager:
    """Thread-safe state machine managing connectivity state and readiness metrics."""

    def __init__(
        self,
        auto_fallback: bool = AUTO_FALLBACK_TO_OLLAMA,
        auto_recover: bool = AUTO_RECOVER_TO_CLOUD,
        health_interval: float = HEALTH_INTERVAL_SECONDS,
    ):
        self._state: ConnectivityState = ConnectivityState.ONLINE
        self._lock = threading.Lock()
        self._last_state_change: float = time.time()
        self._degraded_since: Optional[float] = None
        self._auto_fallback = auto_fallback
        self._auto_recover = auto_recover
        self._health_interval = health_interval
        self._listeners: List[Callable[[ConnectivityState, ConnectivityState, str], Any]] = []

        self._groq = GroqProvider()
        self._ollama = OllamaProvider()

        self._bg_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def current_state(self) -> ConnectivityState:
        # Respect developer forced override
        if os.getenv("KAIROS_FORCE_OFFLINE", "0").lower() in ("1", "true", "yes"):
            return ConnectivityState.OFFLINE
        with self._lock:
            return self._state

    def add_listener(self, callback: Callable[[ConnectivityState, ConnectivityState, str], Any]) -> None:
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[ConnectivityState, ConnectivityState, str], Any]) -> None:
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def transition_to(self, target: ConnectivityState, reason: str = "") -> bool:
        """
        Attempt a state transition adhering to valid transition rules.
        Returns True if transition succeeded, False if disallowed.
        """
        with self._lock:
            current = self._state
            if current == target:
                return True

            allowed = VALID_TRANSITIONS.get(current, set())
            if target not in allowed:
                logger.warning(
                    "[Connectivity] Disallowed transition %s → %s (allowed: %s)",
                    current.value,
                    target.value,
                    [s.value for s in allowed],
                )
                return False

            self._state = target
            self._last_state_change = time.time()
            if target == ConnectivityState.DEGRADED:
                self._degraded_since = time.time()
            elif target != ConnectivityState.DEGRADED:
                self._degraded_since = None

            logger.info("[Connectivity] State changed: %s → %s (reason: %s)", current.value, target.value, reason)
            audit_logger.log_event(
                event_type="CONNECTIVITY_TRANSITION",
                tool_name="connectivity_manager",
                target=target.value,
                outcome="TRANSITION_SUCCESS",
                details={"from": current.value, "to": target.value, "reason": reason},
            )
            listeners_copy = list(self._listeners)

        # Notify listeners outside the lock
        for listener in listeners_copy:
            try:
                listener(current, target, reason)
            except Exception as cb_err:
                logger.error("[Connectivity] Listener error: %s", cb_err)

        return True

    def is_cloud_available(self, timeout: float = 1.5) -> bool:
        """Probe primary cloud provider (Groq) with timeout."""
        health = self._groq.health_check(timeout=timeout)
        return health.available

    def is_ollama_available(self, timeout: float = 1.0) -> bool:
        """Probe local Ollama /api/tags endpoint with timeout."""
        health = self._ollama.health_check(timeout=timeout)
        return health.available

    def check_health_and_update_state(self) -> ConnectivityState:
        """
        Evaluate health checks and advance the state machine.
        Applies debounce so transient glitches do not cause rapid oscillation.
        """
        cloud_ok = self.is_cloud_available(timeout=1.5)
        current = self.current_state()

        if current == ConnectivityState.ONLINE:
            if not cloud_ok:
                self.transition_to(ConnectivityState.DEGRADED, "Cloud health check probe failed")

        elif current == ConnectivityState.DEGRADED:
            if cloud_ok:
                if self._auto_recover:
                    self.transition_to(ConnectivityState.ONLINE, "Cloud recovered quickly")
            else:
                # If degraded for more than 5s, drop to OFFLINE
                elapsed = time.time() - (self._degraded_since or time.time())
                if elapsed >= 4.0:
                    if self._auto_fallback:
                        self.transition_to(ConnectivityState.OFFLINE, "Cloud unreachable after retry window")

        elif current == ConnectivityState.OFFLINE:
            if cloud_ok and self._auto_recover:
                # Detected network life -> enter RECOVERING
                self.transition_to(ConnectivityState.RECOVERING, "Background network check detected connectivity")

        elif current == ConnectivityState.RECOVERING:
            if cloud_ok:
                # Full Groq verification passed -> restore ONLINE
                self.transition_to(ConnectivityState.ONLINE, "Full Groq verification passed")
            else:
                # Flickered back off -> return to OFFLINE
                self.transition_to(ConnectivityState.OFFLINE, "Cloud probe failed during recovery verification")

        return self.current_state()

    def get_readiness_report(self) -> Dict[str, Any]:
        """
        Returns full Local Readiness Panel checklist per spec.
        """
        ollama_health = self._ollama.health_check(timeout=1.0)
        models_status = ollama_health.models_status

        # STT availability (faster-whisper)
        stt_ready = False
        try:
            import transcriber
            stt_ready = getattr(transcriber, "WhisperModel", None) is not None or os.path.exists(
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
            )
        except Exception:
            stt_ready = False

        # TTS offline voice availability (Piper)
        tts_ready = False
        try:
            from providers import piper_tts
            tts_ready = piper_tts.is_piper_available()
        except Exception:
            tts_ready = False

        # Vector memory initialized
        vector_db_ready = False
        try:
            import memory_store
            vector_db_ready = getattr(memory_store, "CHROMA_AVAILABLE", False)
        except Exception:
            vector_db_ready = False

        # RAM & system resource estimation
        mem = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=None)

        return {
            "connectivity_state": self.current_state().value,
            "ollama_installed": ollama_health.details.get("server_online", False),
            "ollama_models": {
                "general": models_status.get(self._ollama.general_model, False),
                "coder": models_status.get(self._ollama.coder_model, False),
                "embed": models_status.get(self._ollama.embed_model, False),
            },
            "required_models_tags": {
                "general": self._ollama.general_model,
                "coder": self._ollama.coder_model,
                "embed": self._ollama.embed_model,
            },
            "all_local_models_ready": ollama_health.available,
            "stt_offline_ready": stt_ready,
            "tts_offline_ready": tts_ready,
            "vector_memory_ready": vector_db_ready,
            "system_resources": {
                "ram_total_gb": round(mem.total / (1024 ** 3), 2),
                "ram_available_gb": round(mem.available / (1024 ** 3), 2),
                "ram_used_percent": mem.percent,
                "cpu_percent": cpu_pct,
            },
            "golden_rule_fallback_message": GOLDEN_RULE_FALLBACK_MESSAGE,
        }

    def start_background_monitor(self, interval: Optional[float] = None) -> None:
        if self._bg_thread and self._bg_thread.is_alive():
            return
        if interval:
            self._health_interval = interval
        self._stop_event.clear()

        def _loop():
            while not self._stop_event.is_set():
                try:
                    self.check_health_and_update_state()
                except Exception as exc:
                    logger.error("[Connectivity] Background loop exception: %s", exc)
                self._stop_event.wait(self._health_interval)

        self._bg_thread = threading.Thread(target=_loop, daemon=True, name="KairosConnectivityMonitor")
        self._bg_thread.start()
        logger.info("[Connectivity] Background monitor started (interval=%.1fs)", self._health_interval)

    def stop_background_monitor(self) -> None:
        self._stop_event.set()
        if self._bg_thread:
            self._bg_thread.join(timeout=2.0)
            self._bg_thread = None


# Singleton instance
connectivity = ConnectivityManager()


def current_state() -> ConnectivityState:
    return connectivity.current_state()


def get_readiness() -> Dict[str, Any]:
    return connectivity.get_readiness_report()


def is_cloud_available(timeout: float = 1.5) -> bool:
    return connectivity.is_cloud_available(timeout=timeout)


def is_ollama_available(timeout: float = 1.0) -> bool:
    return connectivity.is_ollama_available(timeout=timeout)
