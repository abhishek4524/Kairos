import os
import io
import wave
import numpy as np
import warnings

# Suppress annoying warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# ── Load .env manually ────────────────────────────────────────────────────────
_env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(_env_path):
    with open(_env_path, 'r') as _f:
        for _line in _f:
            _line = _line.strip()
            if '=' in _line and not _line.startswith('#'):
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"\''))

# ── STT mode detection ─────────────────────────────────────────────────────────
STT_MODE = os.environ.get("STT_MODE", "api").lower()  # default: groq api first

# ── Conditional imports ────────────────────────────────────────────────────────
try:
    import webrtcvad
    WEBRTCVAD_AVAILABLE = True
except ImportError:
    webrtcvad = None
    WEBRTCVAD_AVAILABLE = False

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

from groq import Groq as _GroqClient
_groq_api_key = os.environ.get("GROQ_API_KEY")
_groq_stt = _GroqClient(api_key=_groq_api_key) if _groq_api_key else None

MODELS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models"))

# ── Whisper Hallucination Phrases (Silence Artifacts) ─────────────────────────
HALLUCINATION_PHRASES = {
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
    "thank you",
    "am i going on it",
    "im going to go",
    "i never gave an answer",
    "connor",
    "kahneman",
    "haneme gel",
    "im mcgowan on it",
    "going on it",
    "palma",
    "sister",
    "oh!",
    "oh.",
    "oh",
}

# Phantom single-word noise tokens to discard when isolated
PHANTOM_SINGLE_WORDS = {
    "oh", "palma", "sister", "you", "so", "and", "the", "on", "it", "a", "huh", "um", "uh"
}


class RealTimeTranscriber:
    def __init__(self, model_size="tiny", device="cuda", compute_type="int8"):
        self.stt_mode = STT_MODE  # 'local' or 'api'
        self.sample_rate = 16000
        self.chunk_duration = 0.25  # Check VAD every 0.25s
        self.chunk_size = int(self.sample_rate * self.chunk_duration)

        # Audio buffer for accumulating stream chunks
        self.audio_buffer = np.array([], dtype=np.float32)
        
        # Endpointing state
        self.speech_buffer = np.array([], dtype=np.float32)
        self.is_speaking = False
        self.silence_chunks = 0
        self.max_silence_chunks = 4  # 4 * 0.25s = 1.0s silence to trigger transcription

        # --- VAD Engine ---
        if WEBRTCVAD_AVAILABLE:
            # Mode 2: aggressive VAD
            self.vad = webrtcvad.Vad(2)
            print("[STT VAD] WebRTC VAD initialized (Aggressiveness=2).")
        else:
            self.vad = None
            print("[STT VAD] WebRTC VAD not available — using RMS energy VAD fallback.")

        # --- VAD & Energy Thresholds (Configurable via Frontend) ---
        self.set_sensitivity("medium")  # default preset: medium
        self.min_speech_ratio = 0.20     # 20% of frames must contain active speech
        self.min_speech_duration = 0.3   # minimum 0.3s duration

        # --- Quality Gates ---
        self.no_speech_prob_threshold = 0.6  # discard if no_speech_prob > 0.6
        self.min_text_chars = 2
        self.min_avg_logprob = -1.5

        # --- Deduplication ---
        self._last_emitted_text = ""
        self._last_emitted_time = 0.0
        self._dedup_window_secs = 2.0

        # --- Continuous speech counter (tracking only, no gate) ---
        self._speech_chunk_count = 0

        # Initialize Local faster-whisper (for local mode or fallback)
        self.local_model = None
        if WhisperModel:
            try:
                print(f"[STT Local] Initializing faster-whisper model '{model_size}' on {device}...")
                self.local_model = WhisperModel(
                    model_size,
                    device=device,
                    compute_type=compute_type,
                    download_root=MODELS_DIR
                )
                print(f"[STT Local] Loaded on {device.upper()}.")
            except Exception as e:
                print(f"[STT Local] CUDA load failed ({e}), falling back to CPU...")
                try:
                    self.local_model = WhisperModel(
                        model_size,
                        device="cpu",
                        compute_type="int8",
                        download_root=MODELS_DIR
                    )
                    print("[STT Local] Loaded on CPU.")
                except Exception as ex:
                    print(f"[STT Local] Failed to load local model: {ex}")

    def set_sensitivity(self, level_or_val):
        """
        Dynamically adjust VAD threshold:
          'low' / 0.003: Sensitive (quiet room / soft voice)
          'medium' / 0.005: Balanced (standard speech, default)
          'high' / 0.012: Strict (noisy room)
        """
        if isinstance(level_or_val, (int, float)):
            self.vad_threshold = float(level_or_val)
        elif str(level_or_val).lower() == "low":
            self.vad_threshold = 0.003
            if self.vad: self.vad.set_mode(1)
        elif str(level_or_val).lower() == "high":
            self.vad_threshold = 0.012
            if self.vad: self.vad.set_mode(3)
        else:  # medium / default
            self.vad_threshold = 0.005
            if self.vad: self.vad.set_mode(2)

        print(f"[STT VAD Config] Sensitivity set to '{level_or_val}' (RMS Threshold = {self.vad_threshold:.4f})")

    # ──────────────────────────────────────────────────────────────────────── #
    #  Multi-Layer VAD: RMS Energy + WebRTC VAD Frame Analysis                #
    # ──────────────────────────────────────────────────────────────────────── #
    def _is_speech(self, audio_array: np.ndarray) -> bool:
        """
        Returns True if the buffer contains valid human speech energy.
        Applies RMS amplitude check + 30ms WebRTC VAD frame ratio check.
        """
        # 1. RMS Energy Check
        rms = float(np.sqrt(np.mean(audio_array ** 2)))
        if rms < self.vad_threshold:
            self._speech_chunk_count = 0
            return False

        # 2. (Removed duration gate for VAD frames, handled at endpointing level)

        # 3. WebRTC VAD Frame Analysis (30ms frames @ 16kHz = 480 samples)
        if self.vad:
            frame_len = int(0.03 * self.sample_rate)  # 480 samples
            pcm_int16 = np.clip(audio_array, -1.0, 1.0)
            pcm_int16 = (pcm_int16 * 32767).astype(np.int16)
            pcm_bytes = pcm_int16.tobytes()

            total_frames = 0
            speech_frames = 0

            for i in range(0, len(pcm_bytes) - (frame_len * 2), frame_len * 2):
                chunk = pcm_bytes[i:i + (frame_len * 2)]
                total_frames += 1
                try:
                    if self.vad.is_speech(chunk, self.sample_rate):
                        speech_frames += 1
                except Exception:
                    pass

            speech_ratio = speech_frames / max(total_frames, 1)
            if speech_ratio < self.min_speech_ratio:
                self._speech_chunk_count = 0
                return False

        self._speech_chunk_count += 1
        return True

    def get_speech_chunk_count(self) -> int:
        return self._speech_chunk_count

    # ──────────────────────────────────────────────────────────────────────── #
    #  Hallucination & Artifact Filters                                       #
    # ──────────────────────────────────────────────────────────────────────── #
    def _is_hallucination_or_garbage(self, text: str) -> bool:
        stripped = text.strip()
        lower = stripped.lower()
        clean = lower.replace(".", "").replace(",", "").replace("?", "").replace("!", "").replace("'", "").strip()

        # Empty or too short
        if len(stripped) < self.min_text_chars:
            return True

        # Pure non-verbal or punctuation
        import re as _re
        if _re.fullmatch(r'[\W\s]+', stripped):
            return True

        # Matches known hallucination phrases
        if clean in HALLUCINATION_PHRASES or lower in HALLUCINATION_PHRASES:
            print(f"[STT Filter] Blocked hallucination phrase: '{stripped}'")
            return True

        for phrase in HALLUCINATION_PHRASES:
            if len(phrase) > 4 and phrase in lower:
                print(f"[STT Filter] Blocked contained hallucination: '{stripped}'")
                return True

        # Single phantom word check
        words = clean.split()
        if len(words) == 1 and words[0] in PHANTOM_SINGLE_WORDS:
            print(f"[STT Filter] Blocked single phantom word: '{stripped}'")
            return True

        # Non-target language script check (Japanese/Chinese/Korean artifacts)
        if _re.search(r'[\u3000-\u9fff\uac00-\ud7af\u30a0-\u30ff]', stripped):
            print(f"[STT Filter] Blocked foreign script artifact: '{stripped}'")
            return True

        return False

    def _is_duplicate(self, text: str) -> bool:
        import time as _time
        now = _time.time()
        norm = ' '.join(text.lower().split())
        last_norm = ' '.join(self._last_emitted_text.lower().split())

        if (now - self._last_emitted_time) >= self._dedup_window_secs:
            self._last_emitted_text = text
            self._last_emitted_time = now
            return False

        if norm == last_norm:
            return True

        if len(norm) < len(last_norm) and last_norm.startswith(norm):
            return True

        self._last_emitted_text = text
        self._last_emitted_time = now
        return False

    # ──────────────────────────────────────────────────────────────────────── #
    #  Main Entrypoint: Audio Chunk Processing                                #
    # ──────────────────────────────────────────────────────────────────────── #
    def process_audio_chunk(self, audio_data: bytes, expected_lang: str = "auto"):
        chunk_array = np.frombuffer(audio_data, dtype=np.float32)
        self.audio_buffer = np.concatenate((self.audio_buffer, chunk_array))

        if len(self.audio_buffer) >= self.chunk_size:
            buffer_to_process = self.audio_buffer[:self.chunk_size].copy()
            
            # Remove processed audio from buffer
            self.audio_buffer = self.audio_buffer[self.chunk_size:]

            # ── VAD GATE ──
            has_speech = self._is_speech(buffer_to_process)
            
            if has_speech:
                self.is_speaking = True
                self.silence_chunks = 0
                self.speech_buffer = np.concatenate((self.speech_buffer, buffer_to_process))
                return None
            else:
                if self.is_speaking:
                    # Trailing silence
                    self.speech_buffer = np.concatenate((self.speech_buffer, buffer_to_process))
                    self.silence_chunks += 1
                    
                    if self.silence_chunks >= self.max_silence_chunks:
                        # Endpoint reached, proceed to transcribe
                        self.is_speaking = False
                        self.silence_chunks = 0
                        buffer_to_transcribe = self.speech_buffer.copy()
                        self.speech_buffer = np.array([], dtype=np.float32)
                        
                        # Only transcribe if the speech is long enough
                        if len(buffer_to_transcribe) / self.sample_rate < self.min_speech_duration:
                            return None
                    else:
                        return None
                else:
                    return None

            print(f"[STT] Endpoint reached. Transcribing {len(buffer_to_transcribe)/self.sample_rate:.1f}s audio. Mode={self.stt_mode}")

            # Primary Path: Groq API; Fallback: Local faster-whisper
            text = ""
            detected_lang = expected_lang if (expected_lang and expected_lang != "auto") else "en"

            if _groq_stt and self.stt_mode in ("api", "groq", "local"):
                text, detected_lang = self._transcribe_groq_api(buffer_to_transcribe, expected_lang)
                if text:
                    print(f"[STT] Groq result: '{text}' (lang={detected_lang})")
                else:
                    print("[STT] Groq returned empty, trying local fallback...")

            if not text and self.local_model:
                text, detected_lang = self._transcribe_local(buffer_to_transcribe, expected_lang)
                if text:
                    print(f"[STT] Local result: '{text}' (lang={detected_lang})")

            if not text or not text.strip():
                return None

            if self._is_hallucination_or_garbage(text):
                return None

            if self._is_duplicate(text):
                return None

            return {"text": text.strip(), "language": detected_lang}

        return None

    # ──────────────────────────────────────────────────────────────────────── #
    #  Primary: Groq Whisper API (whisper-large-v3) with verbose_json          #
    # ──────────────────────────────────────────────────────────────────────── #
    def _transcribe_groq_api(self, audio_array: np.ndarray, expected_lang: str = "auto"):
        try:
            # Prepare in-memory 16kHz 16-bit WAV
            wav_buf = io.BytesIO()
            with wave.open(wav_buf, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                pcm_int16 = np.clip(audio_array, -1.0, 1.0)
                pcm_int16 = (pcm_int16 * 32767).astype(np.int16)
                wf.writeframes(pcm_int16.tobytes())

            wav_buf.seek(0)
            wav_buf.name = "speech.wav"

            kwargs = {
                "file": wav_buf,
                "model": "whisper-large-v3",
                "response_format": "verbose_json",
                "temperature": 0.0,
            }
            if expected_lang and expected_lang != "auto":
                kwargs["language"] = expected_lang

            res = _groq_stt.audio.transcriptions.create(**kwargs)

            # Extract text & language detection
            text = getattr(res, "text", "") or ""
            detected_lang = getattr(res, "language", expected_lang or "en")

            # Inspect segments for no_speech_prob — segments are dicts from Groq API
            segments = getattr(res, "segments", []) or []
            if segments:
                # segments are dicts: {"no_speech_prob": 0.94, ...}
                no_speech_probs = [
                    s["no_speech_prob"] if isinstance(s, dict) and "no_speech_prob" in s
                    else getattr(s, "no_speech_prob", 0.0)
                    for s in segments
                ]
                avg_nsp = sum(no_speech_probs) / max(len(no_speech_probs), 1)
                print(f"[Groq STT] no_speech_prob avg={avg_nsp:.3f} (threshold={self.no_speech_prob_threshold})")
                if avg_nsp > self.no_speech_prob_threshold:
                    print(f"[Groq STT] Discarded — high no_speech_prob: {no_speech_probs}")
                    return "", detected_lang

            return text.strip(), detected_lang

        except Exception as e:
            print(f"[Groq STT API Error] {e} — attempting local fallback...")
            return "", expected_lang

    # ──────────────────────────────────────────────────────────────────────── #
    #  Fallback: Local faster-whisper                                          #
    # ──────────────────────────────────────────────────────────────────────── #
    def _transcribe_local(self, audio_array: np.ndarray, expected_lang: str = "auto"):
        if not self.local_model:
            return "", expected_lang

        try:
            kwargs = {
                "beam_size": 1,
                "vad_filter": True,
                "vad_parameters": {"min_silence_duration_ms": 300, "threshold": 0.5},
                "no_speech_threshold": self.no_speech_prob_threshold,
                "condition_on_previous_text": False,
            }
            if expected_lang and expected_lang != "auto":
                kwargs["language"] = expected_lang

            segments, info = self.local_model.transcribe(audio_array, **kwargs)

            # Check overall no_speech_prob
            if getattr(info, "no_speech_prob", 0.0) > self.no_speech_prob_threshold:
                print(f"[Local STT] Discarded high no_speech_prob ({info.no_speech_prob:.2f})")
                return "", info.language

            kept_text = []
            for seg in segments:
                if getattr(seg, "no_speech_prob", 0.0) > self.no_speech_prob_threshold:
                    continue
                if seg.avg_logprob < self.min_avg_logprob:
                    continue
                kept_text.append(seg.text)

            return "".join(kept_text).strip(), info.language
        except Exception as e:
            print(f"[Local STT Error] {e}")
            return "", expected_lang
