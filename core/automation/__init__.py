"""Automation package with parser, registry, executor, and handlers."""

from .parser import CommandParser
from .registry import CommandRegistry
from .executor import CommandExecutor
from .security import AutomationSecurityPolicy
from .plugin_loader import load_plugins

__all__ = [
    "CommandParser",
    "CommandRegistry",
    "CommandExecutor",
    "AutomationSecurityPolicy",
    "load_plugins",
]
