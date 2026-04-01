"""Offline-first voice engine with wake-word activation and TTS responses."""

from __future__ import annotations

import json
import queue
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import pyttsx3
import sounddevice as sd
from vosk import KaldiRecognizer, Model


class VoiceEngine:
    def __init__(self, model_path: str = "model", wake_word: str = "jarvis"):
        self.q: "queue.Queue[bytes]" = queue.Queue()
        self.wake_word = (wake_word or "jarvis").strip().lower()
        self.active = False
        self._stop = False
        self.active_timeout = 5.0
        self._last_active_ts = 0.0
        self._thread: Optional[threading.Thread] = None

        self.model_path = Path(model_path)
        self.model = Model(str(self.model_path)) if self.model_path.exists() else None
        self.recognizer = KaldiRecognizer(self.model, 16000) if self.model else None

        self.tts = pyttsx3.init()
        self.tts.setProperty("rate", 170)

    def callback(self, indata, _frames, _time, _status):
        self.q.put(bytes(indata))

    def stop(self) -> None:
        self._stop = True

    def start(self) -> None:
        """Start listening on a background daemon thread."""
        self._stop = False
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self.listen, daemon=True)
        self._thread.start()

    def listen(self):
        """Continuous listen loop using Vosk when model is available.

        If the model directory is missing, the engine falls back to text input mode.
        """
        self._stop = False

        if self.recognizer is None:
            print(f"Voice model not found at '{self.model_path}'. Falling back to text mode.")
            while not self._stop:
                try:
                    text = input("voice> ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not text:
                    continue
                self.process(text)
            return

        with sd.RawInputStream(
            samplerate=16000,
            blocksize=4000,
            dtype="int16",
            channels=1,
            callback=self.callback,
        ):
            print("Listening...")
            while not self._stop:
                if self.active and self._last_active_ts > 0 and (time.time() - self._last_active_ts) > self.active_timeout:
                    self.active = False
                    print("Wake window expired; returning to passive mode")
                data = self.q.get()
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = str(result.get("text", "")).strip()
                    if text:
                        print("Heard:", text)
                        self.process(text)
                else:
                    partial = json.loads(self.recognizer.PartialResult())
                    partial_text = str(partial.get("partial", "")).strip()
                    if partial_text:
                        print("Partial:", partial_text)

    def process(self, text: str):
        spoken = (text or "").strip().lower()
        if not spoken:
            return

        if not self.active:
            if self.wake_word in spoken:
                self.active = True
                self._last_active_ts = time.time()
                self.speak_async("Yes?")
            return

        if "stop listening" in spoken:
            self.active = False
            self.speak_async("Going silent.")
            return

        response = self.handle_command(spoken)
        self._last_active_ts = time.time()
        self.speak_async(self._compact_response(response))

    def handle_command(self, text: str):
        """Hook for integration. Override or assign from caller."""
        return f"Executing: {text}"

    def speak(self, text: str):
        message = str(text or "").strip()
        if not message:
            return
        print("Jarvis:", message)
        self.tts.say(message)
        self.tts.runAndWait()

    def speak_async(self, text: str) -> None:
        threading.Thread(target=self.speak, args=(text,), daemon=True).start()

    def _compact_response(self, text: str) -> str:
        message = str(text or "").strip()
        if not message:
            return message
        replacements = {
            "Opening Google Chrome for you now": "Opening Chrome",
            "Launching spotify": "Opening Spotify",
            "Searching for": "Searching",
        }
        for src, dst in replacements.items():
            if src.lower() in message.lower():
                return dst
        parts = message.split("\n")
        return parts[0].strip() if parts else message

    def start_wake_loop(self, callback: Callable[[str], None]) -> None:
        """Compatibility wrapper for previous call sites."""
        self.handle_command = lambda text: str(callback(text) or "Done")
        self.listen()
