"""Dynamic plugin loading for command extensions."""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import List

from .registry import CommandRegistry


def load_plugins(plugin_dir: str, registry: CommandRegistry, logger: logging.Logger | None = None) -> List[str]:
    """Load plugins from a directory; each plugin must expose register(registry)."""
    log = logger or logging.getLogger(__name__)
    root = Path(plugin_dir)
    if not root.exists() or not root.is_dir():
        return []

    loaded: List[str] = []
    for file_path in sorted(root.glob("*.py")):
        if file_path.name.startswith("_"):
            continue

        module_name = f"jarvis_plugin_{file_path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, str(file_path))
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            register = getattr(module, "register", None)
            if callable(register):
                register(registry)
                loaded.append(file_path.stem)
        except Exception as exc:
            log.warning("Failed loading plugin %s: %s", file_path, exc)

    return loaded
