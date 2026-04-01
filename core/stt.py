# pyright: reportUndefinedVariable=false, reportMissingImports=false
"""Speech-to-text compatibility module.

This project previously contained a full duplicated copy of `core/chatbot.py`
inside this file. To remove duplication, this module now delegates shared
conversation logic to `core.chatbot` and only exposes STT-facing wrappers.
"""

import array
import os
import queue
import threading
import time
from typing import Callable, Optional
import requests

try:
    import numpy as np
except Exception:
    np = None

from .utils import env_get, load_env_map
from .resilience import ServiceError, ServiceRequestError, retry_with_backoff, validate_http_status

try:
    import speech_recognition as sr
except Exception:
    sr = None

from .vad_detector import VADDetector


_ENV = load_env_map(".env")
_DEEPGRAM_API_KEY = env_get("DEEPGRAM_API_KEY", "Deepgram_API_KEY", env_map=_ENV)


class EnhancedChromeOnlySpeechRecognition:
    """Simple speech recognizer wrapper with graceful fallback."""

    def __init__(self, language: str = "en-US"):
        self.language = language
        self.recognizer = sr.Recognizer() if sr else None
        self.last_error = ""
        self.stream_mode = False
        self._continuous_thread = None
        self._stop_event = threading.Event()
        self._final_transcripts: queue.Queue[str] = queue.Queue()
        self._interim_transcript = ""
        self._speech_detected_callback: Optional[Callable[[str], None]] = None
        self._latency_target_ms = int(float(os.getenv("JARVIS_STT_TARGET_LATENCY_MS", "300")))
        vad_sensitivity = float(os.getenv("JARVIS_VAD_SENSITIVITY", "0.7"))
        max_silence = float(os.getenv("JARVIS_MAX_SILENCE_SECONDS", "1.2"))
        self.vad = VADDetector(sensitivity=vad_sensitivity, max_silence_seconds=max_silence)

    def _set_last_error(self, message: str = ""):
        self.last_error = str(message or "").strip()

    def _probe_microphone(self) -> bool:
        if not sr:
            self._set_last_error("SpeechRecognition backend is unavailable")
            return False

        try:
            with sr.Microphone():
                pass
            self._set_last_error("")
            return True
        except Exception as exc:
            self._set_last_error(f"Microphone init failed: {exc}")
            return False

    def get_last_error(self) -> str:
        return self.last_error

    def _transcribe_with_deepgram(self, wav_bytes: bytes) -> Optional[str]:
        if not _DEEPGRAM_API_KEY:
            return None
        try:
            def _op():
                try:
                    return requests.post(
                        "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true",
                        headers={
                            "Authorization": f"Token {_DEEPGRAM_API_KEY}",
                            "Content-Type": "audio/wav",
                        },
                        data=wav_bytes,
                        timeout=20,
                    )
                except requests.RequestException as exc:
                    raise ServiceRequestError(str(exc)) from exc

            response = retry_with_backoff(_op, retries=1, base_delay=0.2)
            validate_http_status(response.status_code, "deepgram")
            payload = response.json()
            channels = payload.get("results", {}).get("channels", [])
            if not channels:
                return None
            alternatives = channels[0].get("alternatives", [])
            if not alternatives:
                return None
            transcript = alternatives[0].get("transcript", "").strip()
            return transcript or None
        except ServiceError:
            return None
        except Exception:
            return None

    def listen_once(self, timeout: int = 5, phrase_time_limit: int = 8) -> Optional[str]:
        if not self.recognizer or not sr:
            self._set_last_error("Speech recognizer is unavailable")
            return None

        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            try:
                text = self.recognizer.recognize_google(audio, language=self.language)
                if text:
                    self._set_last_error("")
                    return text
            except Exception:
                pass

            deepgram_text = self._transcribe_with_deepgram(audio.get_wav_data())
            if deepgram_text:
                self._set_last_error("")
                return deepgram_text

            self._set_last_error("No speech recognized")
            return None
        except Exception as exc:
            self._set_last_error(f"Microphone capture failed: {exc}")
            return None

    def start_continuous_listening(self) -> bool:
        if self.stream_mode:
            return True
        if not self.recognizer or not sr:
            self._set_last_error("Speech recognizer is unavailable")
            return False

        preflight_enabled = os.getenv("JARVIS_STT_PREFLIGHT_CHECK", "1") == "1"
        if preflight_enabled and not self._probe_microphone():
            return False

        self.stream_mode = True
        self._stop_event.clear()
        self._continuous_thread = threading.Thread(target=self._continuous_loop, daemon=True)
        self._continuous_thread.start()
        return True

    def stop_continuous_listening(self):
        self.stream_mode = False
        self._stop_event.set()
        if self._continuous_thread and self._continuous_thread.is_alive():
            try:
                self._continuous_thread.join(timeout=1.2)
            except Exception:
                pass
        self._continuous_thread = None

    def get_interim_transcript(self) -> str:
        return (self._interim_transcript or "").strip()

    def get_final_transcript(self, timeout: float = 0.0) -> Optional[str]:
        try:
            return self._final_transcripts.get(timeout=max(0.0, float(timeout)))
        except queue.Empty:
            return None

    def on_speech_detected(self, callback: Optional[Callable[[str], None]] = None):
        if callback is None:
            if self._speech_detected_callback and self._interim_transcript.strip():
                try:
                    self._speech_detected_callback(self._interim_transcript.strip())
                except Exception:
                    pass
            return
        self._speech_detected_callback = callback

    def _continuous_loop(self):
        phrase_limit = max(0.6, min(2.0, self._latency_target_ms / 1000.0))
        rolling_parts = []
        last_activity_ts = 0.0

        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.3)

                while not self._stop_event.is_set():
                    try:
                        audio = self.recognizer.listen(source, timeout=0.45, phrase_time_limit=phrase_limit)
                    except Exception:
                        if rolling_parts and self.vad.should_finalize(time.time() - last_activity_ts):
                            self._finalize_rolling(rolling_parts)
                            rolling_parts = []
                            self._interim_transcript = ""
                        continue

                    raw = b""
                    try:
                        raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
                    except Exception:
                        pass

                    energy = self._estimate_rms_energy(raw)
                    vad_result = self.vad.update(energy)

                    if not vad_result.is_speech:
                        if rolling_parts and self.vad.should_finalize(vad_result.silence_seconds):
                            self._finalize_rolling(rolling_parts)
                            rolling_parts = []
                            self._interim_transcript = ""
                        continue

                    text = None
                    try:
                        text = self.recognizer.recognize_google(audio, language=self.language)
                    except Exception:
                        try:
                            text = self._transcribe_with_deepgram(audio.get_wav_data())
                        except Exception:
                            text = None

                    text = (text or "").strip()
                    if not text:
                        continue

                    rolling_parts.append(text)
                    self._interim_transcript = " ".join(rolling_parts).strip()
                    last_activity_ts = time.time()

                    if self._speech_detected_callback:
                        try:
                            self._speech_detected_callback(self._interim_transcript)
                        except Exception:
                            pass
        except Exception as exc:
            self._set_last_error(f"Continuous listening failed: {exc}")
            return

    def _finalize_rolling(self, rolling_parts):
        finalized = " ".join([part.strip() for part in rolling_parts if str(part).strip()]).strip()
        if finalized:
            self._final_transcripts.put(finalized)

    def _estimate_rms_energy(self, raw_bytes: bytes) -> float:
        if not raw_bytes:
            return 0.0
        try:
            if np is not None:
                samples = np.frombuffer(raw_bytes, dtype=np.int16)
                if samples.size == 0:
                    return 0.0
                return float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))

            samples = array.array("h")
            samples.frombytes(raw_bytes)
            if not samples:
                return 0.0
            square_sum = 0.0
            for value in samples:
                square_sum += float(value) * float(value)
            return (square_sum / float(len(samples))) ** 0.5
        except Exception:
            return 0.0


class WorkingSpeechRecognition(EnhancedChromeOnlySpeechRecognition):
    pass


__all__ = [
    "EnhancedChromeOnlySpeechRecognition",
    "WorkingSpeechRecognition",
]
