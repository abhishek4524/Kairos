import os
import io
import numpy as np
import warnings

# Suppress annoying warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# ── Load .env manually (same approach as llm_agent.py) ────────────────────────
_env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(_env_path):
    with open(_env_path, 'r') as _f:
        for _line in _f:
            _line = _line.strip()
            if '=' in _line and not _line.startswith('#'):
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"\''))

# ── STT mode detection ─────────────────────────────────────────────────────────
STT_MODE = os.environ.get("STT_MODE", "local").lower()

# ── Conditional imports ────────────────────────────────────────────────────────
if STT_MODE == "local":
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        WhisperModel = None
        print("[WARNING] faster-whisper not installed. Local STT will fail.")
    MODELS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models"))

elif STT_MODE == "api":
    from groq import Groq as _GroqClient
    _groq_stt = _GroqClient(api_key=os.environ.get("GROQ_API_KEY"))
else:
    raise ValueError(f"[STT] Unknown STT_MODE='{STT_MODE}'. Must be 'local' or 'api'.")

# ── Hallucination phrases (shared by both modes) ───────────────────────────────
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
    "ご視聴ありがとうございました",
    "transcribed by",
    "[music]",
    "[applause]",
    "(music)",
]


class RealTimeTranscriber:
    def __init__(self, model_size="tiny", device="cuda", compute_type="int8"):
        self.stt_mode = STT_MODE

        # ── LOCAL mode: load faster-whisper ───────────────────────────────────
        if self.stt_mode == "local":
            if WhisperModel is None:
                raise RuntimeError("faster-whisper is not installed. Use STT_MODE=api or pip install faster-whisper")
            print(f"[STT] Running in LOCAL mode (faster-whisper GPU/CPU)")
            print(f"Loading faster-whisper model '{model_size}' on {device}...")
            try:
                self.model = WhisperModel(
                    model_size,
                    device=device,
                    compute_type=compute_type,
                    download_root=MODELS_DIR
                )
                print(f"[STT] faster-whisper model loaded on {device.upper()}.")
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
                print("[STT] faster-whisper model loaded on CPU.")

        # ── API mode: no model loading needed ─────────────────────────────────
        elif self.stt_mode == "api":
            print("[STT] Running in API mode (Groq Whisper API)")
            print("[STT] No local model loaded — transcription will use Groq cloud API.")
            self.model = None

        # Audio buffer for accumulating chunks
        self.audio_buffer = np.array([], dtype=np.float32)

        # Settings
        self.sample_rate   = 16000
        self.chunk_duration = 0.5   # 0.5s chunks
        self.chunk_size    = int(self.sample_rate * self.chunk_duration)

        # --- VAD Settings ---
        self.vad_threshold        = 0.022   # raised from 0.012 — eliminates background noise false-triggers
        self.vad_min_active_ratio = 0.08    # 8% of frames must be active (up from 2%)
        self.min_speech_duration  = 0.4     # minimum 0.4s of continuous speech before STT

        # --- Transcription Quality Filters ---
        self.min_word_count  = 1       # allow single-word greetings
        self.min_avg_logprob = -1.5    # permissive threshold — Hindi names & short phrases score low
        self.min_text_chars  = 3       # discard single-char or 2-char garbage like "6", "A."

        # --- Deduplication: suppress identical partial re-transcriptions ---
        self._last_emitted_text  = ""
        self._last_emitted_time  = 0.0
        self._dedup_window_secs  = 2.0   # same phrase within 2s = suppress

        # --- Continuous speech tracking (for barge-in debounce) ---
        self._speech_chunk_count   = 0     # consecutive chunks VAD considers speech
        self._bargeIn_min_chunks   = 2     # need 2 consecutive speech chunks (~0.5s) before barge-in

    # ──────────────────────────────────────────────────────────────────────── #
    #  VAD: Simple energy-based Voice Activity Detection                        #
    # ──────────────────────────────────────────────────────────────────────── #
    def _is_speech(self, audio_array: np.ndarray) -> bool:
        """Returns True if the buffer contains sustained, loud-enough speech energy."""
        rms = float(np.sqrt(np.mean(audio_array ** 2)))

        if rms < self.vad_threshold:
            self._speech_chunk_count = 0  # reset consecutive counter on silence
            print(f"[VAD] Silence (RMS={rms:.5f} < {self.vad_threshold}). Skipping STT.")
            return False

        frame_size    = int(0.02 * self.sample_rate)  # 20 ms frames
        frames        = [audio_array[i:i + frame_size]
                         for i in range(0, len(audio_array) - frame_size, frame_size)]
        active_frames = sum(1 for f in frames if np.sqrt(np.mean(f ** 2)) > self.vad_threshold)
        active_ratio  = active_frames / max(len(frames), 1)

        if active_ratio < self.vad_min_active_ratio:
            self._speech_chunk_count = 0
            print(f"[VAD] Sparse activity (ratio={active_ratio:.2f} < {self.vad_min_active_ratio}). Skipping STT.")
            return False

        # --- Minimum speech duration gate ---
        speech_duration = len(audio_array) / self.sample_rate
        if speech_duration < self.min_speech_duration:
            self._speech_chunk_count = 0
            print(f"[VAD] Too short ({speech_duration:.2f}s < {self.min_speech_duration}s). Skipping STT.")
            return False

        self._speech_chunk_count += 1
        print(f"[VAD] Speech detected (RMS={rms:.5f}, active={active_ratio:.2f}, chunks={self._speech_chunk_count}). Running STT.")
        return True

    def get_speech_chunk_count(self) -> int:
        """How many consecutive speech chunks have been seen — used for barge-in debounce."""
        return self._speech_chunk_count

    # ──────────────────────────────────────────────────────────────────────── #
    #  Hallucination filter                                                      #
    # ──────────────────────────────────────────────────────────────────────── #
    def _is_hallucination(self, text: str) -> bool:
        lower = text.lower().strip()
        import re as _re
        # Pure punctuation/whitespace — no real words
        if _re.fullmatch(r'[\W\s]+', lower):
            print(f"[FILTER] Punctuation-only, discarded: '{text.strip()}'")
            return True
        for phrase in HALLUCINATION_PHRASES:
            if phrase in lower:
                print(f"[FILTER] Hallucination phrase blocked: '{text.strip()}'")
                return True
        return False

    def _is_garbage_text(self, text: str) -> bool:
        """Additional gate: reject single-word garbage that slipped past confidence filter.
        Catches: very short strings, non-Latin/non-Devanagari random chars, emoji-only, etc.
        """
        import re as _re
        stripped = text.strip()

        # Too short (e.g. "6", "A.", "Yo")
        if len(stripped) < self.min_text_chars:
            print(f"[GATE] Too short ({len(stripped)} chars), discarded: '{stripped}'")
            return True

        # Contains East Asian / non-target-language characters (Japanese, Chinese, Korean)
        if _re.search(r'[\u3000-\u9fff\uac00-\ud7af\u30a0-\u30ff]', stripped):
            print(f"[GATE] Foreign script detected, discarded: '{stripped}'")
            return True

        # Single word AND looks like a random capitalised name-like token with no context
        words = stripped.split()
        if len(words) == 1:
            word = words[0].strip('.,!?;:\'"')
            # All-caps single word that's not a normal word (e.g. "MUGAD", "VORA")
            if word.isupper() and len(word) > 3:
                print(f"[GATE] All-caps single-word garbage, discarded: '{stripped}'")
                return True

        return False

    def _is_duplicate(self, text: str) -> bool:
        """Suppress repeated partial re-transcriptions from the rolling audio buffer.
        
        Logic:
        - Exact same text within window → suppress
        - New text is SHORTER and old starts-with new → suppress (old was the better version)
        - New text is LONGER → let through (user said more), update register
        - Outside dedup window → always let through
        """
        import time as _time
        now = _time.time()
        normalised      = ' '.join(text.lower().split())
        last_normalised = ' '.join(self._last_emitted_text.lower().split())

        # Outside window → always fresh, let through
        if (now - self._last_emitted_time) >= self._dedup_window_secs:
            self._last_emitted_text = text
            self._last_emitted_time = now
            return False

        # Exact match → suppress
        if normalised == last_normalised:
            print(f"[DEDUP] Suppressed exact repeat: '{text.strip()}'")
            return True

        # New is SHORTER and is a prefix of the old (rolling buffer sent a partial of an already-sent phrase)
        if len(normalised) < len(last_normalised) and last_normalised.startswith(normalised):
            print(f"[DEDUP] Suppressed shorter partial: '{text.strip()}'")
            return True

        # New is LONGER (more content) or genuinely different → let through, update register
        self._last_emitted_text = text
        self._last_emitted_time = now
        return False

    # ──────────────────────────────────────────────────────────────────────── #
    #  Main chunk processor (shared by both modes)                               #
    # ──────────────────────────────────────────────────────────────────────── #
    def process_audio_chunk(self, audio_data: bytes, expected_lang: str = "en"):
        """
        Receives raw float32 PCM bytes, appends to buffer, runs VAD,
        and only calls STT when real speech is detected.
        Returns dict with text + language, or None.
        """
        chunk_array       = np.frombuffer(audio_data, dtype=np.float32)
        self.audio_buffer = np.concatenate((self.audio_buffer, chunk_array))

        if len(self.audio_buffer) >= self.chunk_size:
            buffer_to_process = self.audio_buffer.copy()

            # Keep a small 0.5s overlap so we don't cut words at boundaries
            overlap_samples   = int(0.5 * self.sample_rate)
            self.audio_buffer = (self.audio_buffer[-overlap_samples:]
                                 if len(self.audio_buffer) > overlap_samples
                                 else np.array([], dtype=np.float32))

            # --- VAD gate ---
            if not self._is_speech(buffer_to_process):
                return None

            if self.stt_mode == "local":
                text, language = self._transcribe_local(buffer_to_process, expected_lang)
            else:
                text, language = self._transcribe_api(buffer_to_process, expected_lang)

            if not text.strip():
                return None
            if self._is_hallucination(text):
                return None
            if self._is_garbage_text(text):
                return None
            if self._is_duplicate(text):
                return None

            word_count = len(text.strip().split())
            if word_count < self.min_word_count:
                print(f"[FILTER] Too short ({word_count} word(s)), discarded: '{text.strip()}'")
                return None

            return {"text": text.strip(), "language": language}

        return None

    # ──────────────────────────────────────────────────────────────────────── #
    #  LOCAL transcription (faster-whisper)                                     #
    # ──────────────────────────────────────────────────────────────────────── #
    def _transcribe_local(self, audio_array: np.ndarray, expected_lang: str = "en"):
        """Run faster-whisper transcription on the given audio array."""
        kwargs = {
            "beam_size": 1,
            "vad_filter": True,
            "vad_parameters": {
                "min_silence_duration_ms": 300,
                "threshold": 0.5,
            },
            "no_speech_threshold": 0.6,
            "condition_on_previous_text": False,
        }
        if expected_lang and expected_lang != "auto":
            kwargs["language"] = expected_lang

        segments, info = self.model.transcribe(audio_array, **kwargs)

        # Drop unsupported languages unless explicitly requested
        if not ("language" in kwargs) and info.language not in ["en", "hi"] and info.language_probability < 0.85:
            print(f"[FILTER] Dropping unsupported language: {info.language} (prob: {info.language_probability:.2f})")
            return "", info.language

        kept_text = []
        for seg in segments:
            if seg.avg_logprob < self.min_avg_logprob:
                print(f"[CONFIDENCE] Segment dropped (avg_logprob={seg.avg_logprob:.2f}): '{seg.text.strip()}'")
                continue
            kept_text.append(seg.text)

        return "".join(kept_text), info.language

    # ──────────────────────────────────────────────────────────────────────── #
    #  API transcription (Groq Whisper API)                                     #
    # ──────────────────────────────────────────────────────────────────────── #
    def _transcribe_api(self, audio_array: np.ndarray, expected_lang: str = "en"):
        """
        Convert float32 PCM audio to a WAV bytes buffer and send to
        Groq's Whisper API (whisper-large-v3-turbo).
        Returns (text, language_code).
        """
        try:
            import wave, struct

            # Build a minimal WAV in-memory (16kHz, 16-bit, mono)
            wav_buf = io.BytesIO()
            with wave.open(wav_buf, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)           # 16-bit
                wf.setframerate(self.sample_rate)
                # Convert float32 [-1,1] → int16
                pcm_int16 = np.clip(audio_array, -1.0, 1.0)
                pcm_int16 = (pcm_int16 * 32767).astype(np.int16)
                wf.writeframes(pcm_int16.tobytes())

            wav_buf.seek(0)
            wav_buf.name = "audio.wav"   # Groq SDK needs a .name attribute

            kwargs = {
                "file": wav_buf,
                "model": "whisper-large-v3-turbo",
                "response_format": "text",
                "temperature": 0.0,
            }
            if expected_lang and expected_lang != "auto":
                kwargs["language"] = expected_lang

            result = _groq_stt.audio.transcriptions.create(**kwargs)

            # result is a plain string when response_format="text"
            text = result.strip() if isinstance(result, str) else (result.text or "").strip()
            
            # ── Whisper Hallucination Filter ──
            # Whisper often hallucinates these phrases on silence/noise
            _lower = text.lower().replace(".", "").replace(",", "").replace("?", "").replace("!", "").strip()
            _hallucinations = [
                "thank you", "hello", "am i going on it", "im going to go", 
                "i never gave an answer", "subtitles by amaraorg", "connor", 
                "kahneman", "haneme gel", "you", "so", "and then", "on it",
                "im mcgowan on it", "going on it", "on a"
            ]
            if not _lower or _lower in _hallucinations:
                return "", expected_lang

            return text, expected_lang

        except Exception as e:
            print(f"[STT API] Groq Whisper API error: {e}")
            return "", expected_lang

    # ── Legacy public method (keeps backward compatibility if called directly) ─
    def transcribe(self, audio_array: np.ndarray, expected_lang: str = "en"):
        if self.stt_mode == "local":
            return self._transcribe_local(audio_array, expected_lang)
        return self._transcribe_api(audio_array, expected_lang)
