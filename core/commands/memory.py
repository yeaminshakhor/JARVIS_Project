"""Key-value memory service."""

from __future__ import annotations

from typing import Callable, Dict


class MemoryService:
    def __init__(self, memory: Dict[str, str], save_callback: Callable[[], None]):
        self._memory = memory
        self._save = save_callback

    def remember_value(self, payload: str) -> str:
        if "=" not in payload:
            return "Usage: remember <key> = <value>"
        key, value = payload.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if not key:
            return "Memory key is empty"
        self._memory[key] = value
        self._save()
        return f"Saved memory for {key}"

    def recall_value(self, key: str) -> str:
        clean = key.strip().lower()
        if not clean:
            return "Usage: recall <key>"
        value = self._memory.get(clean)
        if value is None:
            return "No memory found"
        return f"{clean}: {value}"

    def list_memory(self) -> str:
        if not self._memory:
            return "No memory saved"
        lines = ["Memory"]
        for key, value in sorted(self._memory.items()):
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)
