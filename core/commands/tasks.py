"""Task management service."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, List, Dict


class TaskService:
    def __init__(self, tasks: List[Dict], save_callback: Callable[[], None]):
        self._tasks = tasks
        self._save = save_callback

    def add_task(self, task_text: str) -> str:
        if not task_text:
            return "Missing task text"
        item = {
            "id": (self._tasks[-1]["id"] + 1) if self._tasks else 1,
            "task": task_text,
            "done": False,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._tasks.append(item)
        self._save()
        return f"Task added #{item['id']}"

    def list_tasks(self) -> str:
        if not self._tasks:
            return "No tasks"
        lines = ["Tasks"]
        for item in self._tasks:
            mark = "done" if item["done"] else "pending"
            lines.append(f"- {item['id']}: [{mark}] {item['task']}")
        return "\n".join(lines)

    def complete_task(self, task_id_text: str) -> str:
        try:
            task_id = int(task_id_text.strip())
        except Exception:
            return "Usage: done task <id>"

        for item in self._tasks:
            if item["id"] == task_id:
                item["done"] = True
                self._save()
                return f"Task #{task_id} marked done"

        return "Task not found"
