import json
import os
import queue
import re
import threading
import time
from datetime import datetime
from typing import List, Optional

import requests

from .tts import _get_tts
from .utils import env_get, load_env_map
from .resilience import ServiceError, ServiceRequestError, retry_with_backoff, validate_http_status
from .paths import LOGS_DIR


class SentenceChunker:
    def __init__(self):
        self._buffer = ""

    def push(self, token: str) -> List[str]:
        if not token:
            return []
        self._buffer += token
        return self._consume_sentences()

    def flush(self) -> Optional[str]:
        tail = self._buffer.strip()
        self._buffer = ""
        return tail or None

    def _consume_sentences(self) -> List[str]:
        out = []
        last_end = 0
        for match in re.finditer(r"(.+?[.!?])(?:\s+|$)", self._buffer, flags=re.DOTALL):
            sentence = match.group(1).strip()
            if sentence:
                out.append(sentence)
            last_end = match.end()
        if last_end > 0:
            self._buffer = self._buffer[last_end:]
        return out


class RealtimeConversationManager:
    def __init__(self, assistant, speech_recognizer):
        self.assistant = assistant
        self.speech_recognizer = speech_recognizer
        self.tts = _get_tts()

        env_map = load_env_map(".env")
        self.openai_api_key = env_get("OPENAI_API_KEY", "OPENAIAPIKEY", "OPEN_AI_API_KEY", env_map=env_map) or ""
        self.stream_model = os.getenv("JARVIS_STREAM_MODEL", "gpt-4o-mini")
        self.enable_stream_llm = os.getenv("JARVIS_USE_STREAMING_LLM", "1") == "1"
        self.pause_timeout = float(os.getenv("JARVIS_VAD_PAUSE_SECONDS", "1.2"))
        self.wake_word = os.getenv("JARVIS_WAKE_WORD", "hey jarvis")
        self.wake_enabled = os.getenv("JARVIS_ENABLE_WAKE_WORD", "1") == "1"
        self.wake_session_timeout = float(os.getenv("JARVIS_WAKE_SESSION_TIMEOUT", "20"))
        self.wake_ack_enabled = os.getenv("JARVIS_WAKE_ACK_ENABLED", "1") == "1"
        self.wake_ack_text = os.getenv("JARVIS_WAKE_ACK_TEXT", "Yes?")
        wake_pattern = r"\s+".join(re.escape(part) for part in self.wake_word.strip().split() if part)
        if not wake_pattern:
            wake_pattern = r"hey\s+jarvis"
        self._wake_word_regex = re.compile(rf"(?:^|\s|[.!?,;:-]){wake_pattern}\b[:,\s-]*(.*)$", flags=re.IGNORECASE)

        self._lock = threading.Lock()
        self._running = False
        self._state = "idle"
        self._session_id = ""
        self._interrupted = False
        self._output_muted = False
        self._last_submitted_text = ""
        self._last_submitted_ts = 0.0
        self._duplicate_suppress_window = float(os.getenv("JARVIS_DUPLICATE_SUPPRESS_SECONDS", "2.2"))
        self._first_token_ts = 0.0
        self._first_audio_ts = 0.0
        self._interrupt_detected_ts = 0.0
        self._metrics_log_file = LOGS_DIR / "realtime_metrics.jsonl"
        self._metrics_log_file.parent.mkdir(parents=True, exist_ok=True)
        self._wake_active = not self.wake_enabled
        self._wake_last_activity_ts = 0.0
        self._wake_just_detected = False

        self._interim_transcript = ""
        self._final_transcript = ""
        self._assistant_partial = ""
        self._assistant_chunks_ready: List[str] = []

        self._history: List[dict] = []
        self._incoming_text_queue: queue.Queue[str] = queue.Queue()
        self._tts_queue: queue.Queue[str] = queue.Queue()

        self._listener_thread = None
        self._processor_thread = None
        self._speaker_thread = None
        self._use_continuous_stt = False

        self._stop_event = threading.Event()
        self._interrupt_event = threading.Event()

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._state = "listening" if not self.wake_enabled else "sleeping"
            self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._interrupted = False
            self._wake_active = not self.wake_enabled
            self._wake_last_activity_ts = time.time()
            self._wake_just_detected = False
            self._interim_transcript = ""
            self._final_transcript = ""
            self._assistant_partial = ""
            self._assistant_chunks_ready.clear()

        self._stop_event.clear()
        self._interrupt_event.clear()

        self._use_continuous_stt = False
        try:
            if hasattr(self.speech_recognizer, "start_continuous_listening"):
                self._use_continuous_stt = bool(self.speech_recognizer.start_continuous_listening())
        except Exception:
            self._use_continuous_stt = False

        self._listener_thread = threading.Thread(target=self._listener_loop, daemon=True)
        self._processor_thread = threading.Thread(target=self._processor_loop, daemon=True)
        self._speaker_thread = threading.Thread(target=self._speaker_loop, daemon=True)

        self._listener_thread.start()
        self._processor_thread.start()
        self._speaker_thread.start()

    def stop(self):
        with self._lock:
            self._running = False
            self._state = "idle"

        self._stop_event.set()
        self._interrupt_event.set()
        try:
            if self._use_continuous_stt and hasattr(self.speech_recognizer, "stop_continuous_listening"):
                self.speech_recognizer.stop_continuous_listening()
        except Exception:
            pass
        try:
            if hasattr(self.tts, "stop_speaking"):
                self.tts.stop_speaking()
            elif hasattr(self.tts, "interrupt"):
                self.tts.interrupt()
        except Exception:
            pass
        self._clear_queue(self._incoming_text_queue)
        self._clear_queue(self._tts_queue)

        for attr in ("_listener_thread", "_processor_thread", "_speaker_thread"):
            worker = getattr(self, attr, None)
            if worker and worker.is_alive():
                try:
                    worker.join(timeout=1.2)
                except Exception:
                    pass
            setattr(self, attr, None)

    def submit_text(self, text: str):
        clean = (text or "").strip()
        if not clean:
            return False
        if self._is_recent_duplicate(clean):
            return False
        now = time.time()
        self._last_submitted_ts = now
        self._first_token_ts = 0.0
        self._first_audio_ts = 0.0
        self._interrupt_detected_ts = 0.0
        self._wake_active = True
        self._wake_last_activity_ts = time.time()
        self._incoming_text_queue.put(clean)
        with self._lock:
            self._final_transcript = clean
            self._state = "thinking"
        return True

    def interrupt(self):
        self._interrupt_detected_ts = time.time()
        self._interrupt_event.set()
        self._interrupted = True
        self._clear_queue(self._tts_queue)
        try:
            if hasattr(self.tts, "stop_speaking"):
                self.tts.stop_speaking()
        except Exception:
            pass
        with self._lock:
            self._state = self._idle_state()
        return True

    def status(self):
        stt_error = ""
        try:
            if hasattr(self.speech_recognizer, "get_last_error"):
                stt_error = str(self.speech_recognizer.get_last_error() or "").strip()
            elif hasattr(self.speech_recognizer, "last_error"):
                stt_error = str(getattr(self.speech_recognizer, "last_error", "") or "").strip()
        except Exception:
            stt_error = ""

        with self._lock:
            payload = {
                "ok": True,
                "session_id": self._session_id,
                "state": self._state,
                "wake_word": self.wake_word,
                "wake_active": self._wake_active,
                "waiting_for_wake": self.wake_enabled and not self._wake_active,
                "wake_just_detected": self._wake_just_detected,
                "interim_transcript": self._interim_transcript,
                "final_transcript": self._final_transcript,
                "assistant_partial": self._assistant_partial,
                "assistant_new_chunks": list(self._assistant_chunks_ready),
                "interrupted": self._interrupted,
                "voice_muted": self._output_muted,
                "stt_error": stt_error,
                "metrics": self._current_metrics(),
                "tts_queue_size": self._tts_queue.qsize(),
            }
            self._final_transcript = ""
            self._assistant_chunks_ready.clear()
            self._interrupted = False
            self._wake_just_detected = False
        return payload

    def set_output_muted(self, muted: bool):
        with self._lock:
            self._output_muted = bool(muted)
        if muted:
            self._clear_queue(self._tts_queue)
        return True

    def _listener_loop(self):
        rolling = ""
        last_speech_time = 0.0

        while not self._stop_event.is_set():
            with self._lock:
                running = self._running
            if not running:
                time.sleep(0.1)
                continue

            transcript = ""
            if self._use_continuous_stt and hasattr(self.speech_recognizer, "get_final_transcript"):
                try:
                    interim = ""
                    if hasattr(self.speech_recognizer, "get_interim_transcript"):
                        interim = str(self.speech_recognizer.get_interim_transcript() or "").strip()
                        if interim:
                            with self._lock:
                                if self._state in {"listening", "sleeping"}:
                                    self._interim_transcript = interim

                    try:
                        transcript = str(self.speech_recognizer.get_final_transcript(timeout=0.18) or "").strip()
                    except TypeError:
                        transcript = str(self.speech_recognizer.get_final_transcript() or "").strip()
                except Exception:
                    transcript = ""
            else:
                try:
                    heard = self.speech_recognizer.listen_once(timeout=2, phrase_time_limit=2)
                except Exception:
                    heard = None
                transcript = str(heard or "").strip()

            now = time.time()

            if self.wake_enabled and self._wake_active and (now - self._wake_last_activity_ts) > self.wake_session_timeout:
                self._wake_active = False
                with self._lock:
                    self._state = "sleeping"

            if transcript:
                if self._state == "speaking":
                    self.interrupt()

                if self.wake_enabled and not self._wake_active:
                    command_tail = self._extract_wake_command(transcript)
                    if command_tail is None:
                        with self._lock:
                            self._state = "sleeping"
                            self._interim_transcript = ""
                        continue

                    self._wake_active = True
                    self._wake_last_activity_ts = now
                    self._wake_just_detected = True

                    if command_tail:
                        rolling = command_tail
                        last_speech_time = now
                        with self._lock:
                            self._state = "listening"
                            self._interim_transcript = rolling
                        continue

                    with self._lock:
                        self._state = "listening"
                        self._interim_transcript = ""

                    if self.wake_ack_enabled and self.wake_ack_text:
                        self._tts_queue.put(self.wake_ack_text)
                        with self._lock:
                            self._assistant_chunks_ready.append(self.wake_ack_text)
                    continue

                if self._use_continuous_stt:
                    finalized = transcript.strip()
                    if self._is_recent_duplicate(finalized):
                        with self._lock:
                            self._interim_transcript = ""
                            self._state = self._idle_state()
                        continue
                    with self._lock:
                        self._interim_transcript = ""
                        self._final_transcript = finalized
                        self._state = "thinking"
                    self._incoming_text_queue.put(finalized)
                    self._wake_last_activity_ts = now
                    continue

                rolling = f"{rolling} {transcript}".strip()
                last_speech_time = now
                self._wake_last_activity_ts = now
                with self._lock:
                    self._state = "listening"
                    self._interim_transcript = rolling
            else:
                if rolling and (now - last_speech_time) >= self.pause_timeout:
                    finalized = rolling.strip()
                    rolling = ""
                    if self._is_recent_duplicate(finalized):
                        with self._lock:
                            self._interim_transcript = ""
                            self._state = self._idle_state()
                        continue
                    with self._lock:
                        self._interim_transcript = ""
                        self._final_transcript = finalized
                        self._state = "thinking"
                    self._incoming_text_queue.put(finalized)

                time.sleep(0.08)

    def _processor_loop(self):
        while not self._stop_event.is_set():
            try:
                text = self._incoming_text_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if not text:
                continue

            with self._lock:
                self._state = "thinking"
                self._wake_last_activity_ts = time.time()

            self._history.append({"role": "user", "content": text})
            chunker = SentenceChunker()
            response_accum = ""
            streamed_any = False

            for token in self._stream_llm_tokens(text):
                if self._stop_event.is_set():
                    break
                if self._interrupt_event.is_set():
                    self._interrupt_event.clear()
                    break

                streamed_any = True
                if self._first_token_ts <= 0:
                    self._first_token_ts = time.time()
                response_accum += token
                with self._lock:
                    self._assistant_partial = response_accum.strip()

                sentences = chunker.push(token)
                for sentence in sentences:
                    self._tts_queue.put(sentence)
                    with self._lock:
                        self._assistant_chunks_ready.append(sentence)

            if not streamed_any:
                fallback = self._assistant_fallback_response(text)
                if self._first_token_ts <= 0:
                    self._first_token_ts = time.time()
                response_accum = fallback
                with self._lock:
                    self._assistant_partial = response_accum
                for sentence in self._split_sentences(fallback):
                    self._tts_queue.put(sentence)
                    with self._lock:
                        self._assistant_chunks_ready.append(sentence)
            else:
                tail = chunker.flush()
                if tail:
                    self._tts_queue.put(tail)
                    with self._lock:
                        self._assistant_chunks_ready.append(tail)

            self._history.append({"role": "assistant", "content": response_accum})
            self._history = self._history[-20:]
            self._wake_last_activity_ts = time.time()
            self._append_metrics_log(text)

    def _speaker_loop(self):
        while not self._stop_event.is_set():
            try:
                chunk = self._tts_queue.get(timeout=0.08)
            except queue.Empty:
                try:
                    if hasattr(self.tts, "is_speaking") and self.tts.is_speaking():
                        with self._lock:
                            self._state = "speaking"
                except Exception:
                    pass
                continue

            if not chunk:
                continue

            if self._interrupt_event.is_set():
                self._interrupt_event.clear()
                continue

            with self._lock:
                self._state = "speaking"

            try:
                if not self._output_muted:
                    if self._first_audio_ts <= 0:
                        self._first_audio_ts = time.time()
                    queued = False
                    if hasattr(self.tts, "speak_streaming"):
                        try:
                            queued = bool(self.tts.speak_streaming(chunk))
                        except Exception:
                            queued = False
                    if not queued:
                        self.tts.speak(chunk)
            except Exception:
                pass

            with self._lock:
                tts_busy = False
                try:
                    if hasattr(self.tts, "is_speaking"):
                        tts_busy = bool(self.tts.is_speaking())
                except Exception:
                    tts_busy = False
                if self._tts_queue.qsize() == 0 and not tts_busy:
                    self._state = self._idle_state()

    def _stream_llm_tokens(self, user_text: str):
        if not (self.enable_stream_llm and self.openai_api_key):
            if os.getenv("JARVIS_STREAMING_MODE", "1") == "1" and not self._looks_like_local_command(user_text):
                try:
                    from .chatbot import stream_response
                    return stream_response(user_text)
                except Exception:
                    return []
            return []

        messages = [
            {"role": "system", "content": "You are Jarvis. Reply concisely and naturally."},
            *self._history,
            {"role": "user", "content": user_text},
        ]

        try:
            def _op():
                try:
                    return requests.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.openai_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.stream_model,
                            "messages": messages,
                            "stream": True,
                            "temperature": 0.6,
                        },
                        stream=True,
                        timeout=60,
                    )
                except requests.RequestException as exc:
                    raise ServiceRequestError(str(exc)) from exc

            response = retry_with_backoff(_op, retries=1, base_delay=0.2)
            validate_http_status(response.status_code, "openai-realtime-stream")

            def token_generator():
                for raw_line in response.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    line = raw_line.strip()
                    if not line.startswith("data:"):
                        continue
                    data_part = line[len("data:"):].strip()
                    if data_part == "[DONE]":
                        break
                    try:
                        payload = json.loads(data_part)
                    except Exception:
                        continue
                    delta = payload.get("choices", [{}])[0].get("delta", {})
                    token = delta.get("content")
                    if token:
                        yield token

            return token_generator()
        except ServiceError:
            return []
        except Exception:
            return []

    def _looks_like_local_command(self, text: str) -> bool:
        low = (text or "").strip().lower()
        if not low:
            return False
        return low.startswith((
            "open ", "close ", "play ", "search ", "download ", "wifi ", "bluetooth ",
            "turn on", "turn off", "add task", "list tasks", "remember ", "recall ",
            "auth ", "system ", "doctor", "status"
        ))

    def _assistant_fallback_response(self, text: str) -> str:
        try:
            reply = self.assistant.process(text)
            return str(reply or "")
        except Exception as exc:
            return f"I had an issue processing that: {exc}"

    def _split_sentences(self, text: str) -> List[str]:
        parts = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
        return [part.strip() for part in parts if part and part.strip()]

    def _clear_queue(self, q: queue.Queue):
        try:
            while True:
                q.get_nowait()
        except queue.Empty:
            return

    def _extract_wake_command(self, transcript: str) -> Optional[str]:
        text = (transcript or "").strip()
        if not text:
            return None

        match = self._wake_word_regex.search(text)
        if not match:
            return None
        return (match.group(1) or "").strip()

    def _idle_state(self) -> str:
        if not self.wake_enabled:
            return "listening"
        if self._wake_active:
            return "listening"
        return "sleeping"

    def _current_metrics(self):
        submitted = self._last_submitted_ts
        first_token_latency_ms = None
        first_audio_latency_ms = None
        interrupt_latency_ms = None

        if submitted > 0 and self._first_token_ts > 0:
            first_token_latency_ms = int((self._first_token_ts - submitted) * 1000)
        if submitted > 0 and self._first_audio_ts > 0:
            first_audio_latency_ms = int((self._first_audio_ts - submitted) * 1000)
        if self._interrupt_detected_ts > 0:
            interrupt_latency_ms = 0

        return {
            "first_token_latency_ms": first_token_latency_ms,
            "first_audio_latency_ms": first_audio_latency_ms,
            "interrupt_response_ms": interrupt_latency_ms,
        }

    def _append_metrics_log(self, user_text: str):
        try:
            payload = {
                "time": datetime.now().isoformat(timespec="seconds"),
                "session_id": self._session_id,
                "input": (user_text or "")[:120],
                **self._current_metrics(),
            }
            with open(self._metrics_log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            return

    def _is_recent_duplicate(self, text: str) -> bool:
        clean = (text or "").strip().lower()
        if not clean:
            return False

        with self._lock:
            now = time.time()
            if self._last_submitted_text == clean and (now - self._last_submitted_ts) <= self._duplicate_suppress_window:
                return True

            self._last_submitted_text = clean
            self._last_submitted_ts = now
            return False
