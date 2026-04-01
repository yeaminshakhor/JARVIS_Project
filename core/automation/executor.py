"""Command executor for parsed automation actions."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .registry import CommandRegistry


class CommandExecutor:
    def __init__(self, registry: CommandRegistry):
        self.registry = registry
        self._thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="jarvis-cmd")

    def execute(self, action: str, **kwargs: Any):
        if action == "multi":
            results = []
            commands = kwargs.get("commands", [])
            if isinstance(commands, list):
                for cmd in commands:
                    if not isinstance(cmd, dict):
                        continue
                    cmd_action = str(cmd.get("action", "")).strip()
                    if not cmd_action:
                        continue
                    cmd_kwargs = {k: v for k, v in cmd.items() if k != "action"}
                    results.append(str(self.execute(cmd_action, **cmd_kwargs)))
            return "\n".join(results)

        spec = self.registry.get(action)
        if not spec:
            return f" Unknown command: {action}"
        return spec.handler(**kwargs)

    async def execute_async(self, action: str, **kwargs: Any):
        """Run command handlers without blocking the caller thread."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._thread_pool, lambda: self.execute(action, **kwargs))
