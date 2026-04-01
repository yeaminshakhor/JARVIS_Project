"""Command registry with metadata for automation actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional


@dataclass(frozen=True)
class CommandSpec:
    name: str
    group: str
    handler: Callable
    permission: str = "basic"


class CommandRegistry:
    def __init__(self):
        self._commands: Dict[str, CommandSpec] = {}

    def register(self, name: str, handler: Callable, *, group: str = "general", permission: str = "basic") -> None:
        self._commands[name] = CommandSpec(name=name, group=group, handler=handler, permission=permission)

    def get(self, name: str) -> Optional[CommandSpec]:
        return self._commands.get(name)

    def handlers(self) -> Dict[str, Callable]:
        return {name: spec.handler for name, spec in self._commands.items()}

    def permissions(self) -> Dict[str, str]:
        return {name: spec.permission for name, spec in self._commands.items()}

    def groups(self) -> Dict[str, str]:
        return {name: spec.group for name, spec in self._commands.items()}

    def list_actions(self):
        return sorted(self._commands.keys())
