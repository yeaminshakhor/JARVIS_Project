from __future__ import annotations

from typing import Any, Dict

try:
    from .realtime_conversation import RealtimeConversationManager
except Exception:  # pragma: no cover - defensive fallback for partial deployments
    RealtimeConversationManager = None
from .state_machine import ConversationState, ConversationStateMachine
from .streaming_pipeline import StreamingPipeline


class ConversationManager:
    """High-level orchestrator facade around realtime conversation engine.

    Keeps explicit state-machine snapshots and queue pipeline objects while
    preserving the existing runtime behavior and bridge API compatibility.
    """

    def __init__(self, assistant, speech_recognizer):
        if RealtimeConversationManager is None:
            raise RuntimeError("RealtimeConversationManager is unavailable. Check core/realtime_conversation.py")
        self.realtime = RealtimeConversationManager(assistant, speech_recognizer)
        self.state_machine = ConversationStateMachine()
        self.pipeline = StreamingPipeline()

    def start(self):
        self.realtime.start()
        self.state_machine.transition(ConversationState.LISTENING, "start")

    def stop(self):
        self.realtime.stop()
        self.pipeline.clear()
        self.state_machine.transition(ConversationState.IDLE, "stop")

    def submit_text(self, text: str):
        accepted = self.realtime.submit_text(text)
        if accepted:
            self.pipeline.user_queue.put(text)
            self.state_machine.transition(ConversationState.PROCESSING, "submit")
        return accepted

    def interrupt(self):
        self.realtime.interrupt()
        self.pipeline.clear()
        self.state_machine.transition(ConversationState.INTERRUPTED, "barge-in")
        return True

    def set_output_muted(self, muted: bool):
        return self.realtime.set_output_muted(muted)

    @property
    def wake_enabled(self):
        return self.realtime.wake_enabled

    @property
    def wake_word(self):
        return self.realtime.wake_word

    def status(self) -> Dict[str, Any]:
        data = self.realtime.status()
        raw_state = str(data.get("state", "idle")).lower().strip()
        mapped = {
            "thinking": ConversationState.PROCESSING,
            "speaking": ConversationState.SPEAKING,
            "listening": ConversationState.LISTENING,
            "interrupted": ConversationState.INTERRUPTED,
            "sleeping": ConversationState.SLEEPING,
            "idle": ConversationState.IDLE,
        }.get(raw_state, ConversationState.IDLE)
        self.state_machine.transition(mapped, "status-sync")
        data["state_machine"] = self.state_machine.snapshot().state.value
        return data
