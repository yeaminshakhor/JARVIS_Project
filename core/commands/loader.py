"""Auto-discovery command loader for automation registry."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from ..automation.plugin_loader import load_plugins
from ..automation.registry import CommandRegistry


def load_all_commands(registry: CommandRegistry, automation, logger: logging.Logger | None = None) -> List[str]:
    """Register built-in automation commands and load external plugins."""
    log = logger or logging.getLogger(__name__)

    builtins = [
        ("open_browser", automation.open_browser, "browser", "basic"),
        ("open_website", automation.open_website, "browser", "basic"),
        ("search_web", automation.search_web, "browser", "basic"),
        ("open_app", automation.open_application, "apps", "basic"),
        ("list_apps", automation.list_installed_apps, "apps", "basic"),
        ("system_info", automation.get_system_info, "system", "basic"),
        ("bluetooth_info", automation.get_bluetooth_info, "system", "basic"),
        ("bluetooth_on", automation.bluetooth_on, "system", "basic"),
        ("bluetooth_off", automation.bluetooth_off, "system", "basic"),
        ("volume_up", automation.volume_up, "system", "basic"),
        ("volume_down", automation.volume_down, "system", "basic"),
        ("mute", automation.mute_volume, "system", "basic"),
        ("shutdown", automation.system_shutdown, "system", "admin"),
        ("restart", automation.system_restart, "system", "admin"),
        ("type_text", automation.type_text, "input", "basic"),
        ("press_keys", automation.press_keys, "input", "basic"),
        ("take_screenshot", automation.take_screenshot, "input", "basic"),
        ("take_photo", automation.take_photo, "device", "basic"),
        ("remember", automation.remember_value, "memory", "basic"),
        ("recall", automation.recall_value, "memory", "basic"),
    ]

    for name, handler, group, permission in builtins:
        registry.register(name, handler, group=group, permission=permission)

    loaded_plugins: List[str] = []
    for plugin_dir in ("plugins", "Plugins"):
        resolved = Path(plugin_dir)
        if not resolved.exists():
            continue
        loaded_plugins.extend(load_plugins(str(resolved), registry, log))

    return loaded_plugins
