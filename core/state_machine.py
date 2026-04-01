from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from time import time
from typing import Optional


class ConversationState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    SLEEPING = "sleeping"


@dataclass
class StateSnapshot:
    state: ConversationState
    updated_at: float
    reason: str = ""


class ConversationStateMachine:
    def __init__(self, initial: ConversationState = ConversationState.IDLE):
        self._lock = threading.Lock()
        self._state = initial
        self._updated_at = time()
        self._reason = "init"

    def transition(self, state: ConversationState, reason: str = "") -> StateSnapshot:
        with self._lock:
            self._state = state
            self._updated_at = time()
            self._reason = reason
            return StateSnapshot(self._state, self._updated_at, self._reason)

    def snapshot(self) -> StateSnapshot:
        with self._lock:
            return StateSnapshot(self._state, self._updated_at, self._reason)

    @property
    def state(self) -> ConversationState:
        with self._lock:
            return self._state
