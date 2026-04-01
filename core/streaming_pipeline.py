from __future__ import annotations

import queue
from typing import Optional


class StreamingPipeline:
    def __init__(self, maxsize: int = 1024):
        self.user_queue: queue.Queue[str] = queue.Queue(maxsize=maxsize)
        self.token_queue: queue.Queue[str] = queue.Queue(maxsize=maxsize)
        self.sentence_queue: queue.Queue[str] = queue.Queue(maxsize=maxsize)
        self.tts_queue: queue.Queue[str] = queue.Queue(maxsize=maxsize)

    def clear(self):
        for q in (self.user_queue, self.token_queue, self.sentence_queue, self.tts_queue):
            self._drain(q)

    def _drain(self, q: queue.Queue):
        try:
            while True:
                q.get_nowait()
        except queue.Empty:
            return

    @staticmethod
    def pop_nowait(q: queue.Queue) -> Optional[str]:
        try:
            return q.get_nowait()
        except queue.Empty:
            return None
