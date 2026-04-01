from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class VADResult:
    is_speech: bool
    energy: float
    threshold: float
    silence_seconds: float


class VADDetector:
    def __init__(self, sensitivity: float = 0.7, max_silence_seconds: float = 1.2):
        self.sensitivity = max(0.05, min(1.0, float(sensitivity)))
        self.max_silence_seconds = max(0.2, float(max_silence_seconds))
        self._noise_floor = 120.0
        self._last_speech_ts = 0.0

    def update(self, energy: float) -> VADResult:
        now = time.time()
        observed = max(0.0, float(energy))
        self._noise_floor = (0.92 * self._noise_floor) + (0.08 * observed)
        threshold = self._noise_floor * (1.05 + (0.85 * self.sensitivity))

        is_speech = observed >= threshold
        if is_speech:
            self._last_speech_ts = now

        silence_seconds = 0.0
        if self._last_speech_ts > 0:
            silence_seconds = max(0.0, now - self._last_speech_ts)

        return VADResult(
            is_speech=is_speech,
            energy=observed,
            threshold=threshold,
            silence_seconds=silence_seconds,
        )

    def should_finalize(self, silence_seconds: float) -> bool:
        return float(silence_seconds) >= self.max_silence_seconds
