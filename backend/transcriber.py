import os
import numpy as np
import sys
import torch  # Importing torch first helps CTranslate2 find CUDA DLLs on Windows
import warnings

# Suppress annoying warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# --- Windows DLL Workaround for CTranslate2 ---
try:
    import site
    for pkg in site.getsitepackages():
        cublas_bin = os.path.join(pkg, "nvidia", "cublas", "bin")
        cudnn_bin = os.path.join(pkg, "nvidia", "cudnn", "bin")
        if os.path.exists(cublas_bin):
            os.environ["PATH"] = cublas_bin + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(cublas_bin)
        if os.path.exists(cudnn_bin):
            os.environ["PATH"] = cudnn_bin + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(cudnn_bin)
except Exception:
    pass

from faster_whisper import WhisperModel

# Path to the models directory
MODELS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models"))

# --- Whisper hallucination phrases to filter out ---
# These are common strings Whisper generates on silence/noise
HALLUCINATION_PHRASES = [
    "thanks for watching",
    "thank you for watching",
    "please subscribe",
    "like and subscribe",
    "see you next time",
    "bye bye",
    "subtitles by",
    "amara.org",
    "www.",
    ".com",
    "ご視聴ありがとうございました",  # Japanese "thanks for watching"
    "transcribed by",
    "[music]",
    "[applause]",
    "(music)",
]

class RealTimeTranscriber:
    def __init__(self, model_size="tiny", device="cuda", compute_type="int8"):
        print(f"Loading faster-whisper model '{model_size}' on {device}...")
        try:
            self.model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
                download_root=MODELS_DIR
            )
            print(f"Model loaded successfully on {device}.")
        except Exception as e:
            print(f"\n[WARNING] Failed to load on GPU (CUDA): {e}")
            if "cublas64_12.dll" in str(e):
                print("--> Missing NVIDIA DLLs. Falling back to CPU...")
                print("--> To fix GPU later, run: pip install nvidia-cublas-cu12 nvidia-cudnn-cu12")
            print(f"Loading faster-whisper model '{model_size}' on CPU instead...")
            self.model = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",
                download_root=MODELS_DIR
            )
            print("Model loaded successfully on CPU.")

        # Audio buffer for accumulating chunks
        self.audio_buffer = np.array([], dtype=np.float32)

        # Settings
        self.sample_rate = 16000
        self.chunk_duration = 0.5   # 0.5s — faster response than 0.8s
        self.chunk_size = int(self.sample_rate * self.chunk_duration)

        # --- VAD Settings ---
        # RMS energy threshold. Lowered to 0.015 to catch softer voices quickly.
        self.vad_threshold = 0.012  # even lower — catch soft voices reliably
        # Minimum fraction of the buffer that must be "active" (above threshold per-frame)
        self.vad_min_active_ratio = 0.04  # 4% — so even short utterances pass

        # --- Transcription Quality Filters ---
        # Discard transcription if word count is below this
        self.min_word_count = 1  # Allow single-word greetings like 'Hi', 'Hello'
        # Relax confidence threshold: -0.8 to catch more real speech
        self.min_avg_logprob = -0.8

    # ------------------------------------------------------------------ #
    #  VAD: Simple energy-based Voice Activity Detection                   #
    # ------------------------------------------------------------------ #
    def _is_speech(self, audio_array: np.ndarray) -> bool:
        """
        Returns True if the buffer contains enough speech energy to warrant
        running Whisper. Filters silence and mic noise.
        """
        # Compute RMS over the whole buffer
        rms = float(np.sqrt(np.mean(audio_array ** 2)))

        if rms < self.vad_threshold:
            print(f"[VAD] Silence detected (RMS={rms:.5f} < {self.vad_threshold}). Skipping Whisper.")
            return False

        # Secondary check: count frames above threshold in 20ms windows
        frame_size = int(0.02 * self.sample_rate)  # 20 ms
        frames = [audio_array[i:i + frame_size]
                  for i in range(0, len(audio_array) - frame_size, frame_size)]
        active_frames = sum(1 for f in frames if np.sqrt(np.mean(f ** 2)) > self.vad_threshold)
        active_ratio = active_frames / max(len(frames), 1)

        if active_ratio < self.vad_min_active_ratio:
            print(f"[VAD] Mostly silence (active_ratio={active_ratio:.2f}). Skipping Whisper.")
            return False

        print(f"[VAD] Speech detected (RMS={rms:.5f}, active={active_ratio:.2f}). Running Whisper.")
        return True

    # ------------------------------------------------------------------ #
    #  Hallucination filter                                                #
    # ------------------------------------------------------------------ #
    def _is_hallucination(self, text: str) -> bool:
        """
        Returns True if the transcribed text looks like a Whisper hallucination
        (common phrases it generates on silence/low-quality audio).
        """
        lower = text.lower().strip()
        for phrase in HALLUCINATION_PHRASES:
            if phrase in lower:
                print(f"[FILTER] Hallucination blocked: '{text.strip()}'")
                return True
        return False

    # ------------------------------------------------------------------ #
    #  Main chunk processor                                                #
    # ------------------------------------------------------------------ #
    def process_audio_chunk(self, audio_data: bytes, expected_lang: str = "en"):
        """
        Receives raw float32 PCM bytes, appends to buffer, runs VAD,
        and only calls Whisper when real speech is detected.
        Returns dict with text + language, or None.
        """
        chunk_array = np.frombuffer(audio_data, dtype=np.float32)
        self.audio_buffer = np.concatenate((self.audio_buffer, chunk_array))

        if len(self.audio_buffer) >= self.chunk_size:
            buffer_to_process = self.audio_buffer.copy()

            # Keep a small 0.5s overlap so we don't cut words at boundaries
            overlap_samples = int(0.5 * self.sample_rate)
            self.audio_buffer = (self.audio_buffer[-overlap_samples:]
                                 if len(self.audio_buffer) > overlap_samples
                                 else np.array([], dtype=np.float32))

            # --- VAD gate: only call Whisper if there's actual speech ---
            if not self._is_speech(buffer_to_process):
                return None

            text, language = self.transcribe(buffer_to_process, expected_lang)

            if not text.strip():
                return None

            # --- Hallucination filter ---
            if self._is_hallucination(text):
                return None

            # --- Minimum word count filter ---
            word_count = len(text.strip().split())
            if word_count < self.min_word_count:
                print(f"[FILTER] Too short ({word_count} word(s)), discarded: '{text.strip()}'")
                return None

            return {"text": text.strip(), "language": language}

        return None

    def transcribe(self, audio_array: np.ndarray, expected_lang: str = "en"):
        """Run faster-whisper transcription on the given audio array."""
        kwargs = {
            "beam_size": 1, # Greedy decoding for ultra-fast speed
            "vad_filter": True,
            "vad_parameters": {
                "min_silence_duration_ms": 300, # Faster VAD silence window
                "threshold": 0.5,
            },
            "no_speech_threshold": 0.6,
            "condition_on_previous_text": False,
        }
        if expected_lang and expected_lang != "auto":
            kwargs["language"] = expected_lang

        segments, info = self.model.transcribe(audio_array, **kwargs)

        # Restrict languages strictly to English or Hindi unless highly confident
        # If we passed a specific language, we relax this restriction
        if not ("language" in kwargs) and info.language not in ["en", "hi"] and info.language_probability < 0.85:
            print(f"[FILTER] Dropping unsupported language: {info.language} (prob: {info.language_probability:.2f})")
            return "", info.language

        # Collect segments and filter out low-confidence ones individually
        kept_text = []
        for seg in segments:
            if seg.avg_logprob < self.min_avg_logprob:
                print(f"[CONFIDENCE] Segment dropped (avg_logprob={seg.avg_logprob:.2f} < {self.min_avg_logprob}): '{seg.text.strip()}'")
                continue
            kept_text.append(seg.text)

        text = "".join(kept_text)
        return text, info.language
