"""Application discovery and launch handlers."""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Dict

from ..constants import BASE_APP_MAP


class ApplicationHandler:
    def __init__(self, os_type: str):
        self.os_type = os_type
        self.installed_apps = self._discover_installed_apps()

    def _discover_installed_apps(self) -> Dict[str, str]:
        apps: Dict[str, str] = {}
        for app_name, commands in BASE_APP_MAP.items():
            apps[app_name] = commands.get(self.os_type, commands.get("linux", ""))
        return apps

    def _is_safe_command_text(self, value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        blocked = [";", "&&", "||", "|", "`", "$(", ">", "<", "\n", "\r"]
        if any(token in text for token in blocked):
            return False
        return bool(re.fullmatch(r"[a-zA-Z0-9_./:+\-\s]+", text))

    def open_application(self, app_name: str = "") -> str:
        clean_name = (app_name or "").strip().lower()
        if not clean_name:
            return " Please provide an application name"
        if clean_name not in self.installed_apps:
            return f" Application not allowlisted: {clean_name}"

        command_text = str(self.installed_apps.get(clean_name, "")).strip()
        if not command_text or not self._is_safe_command_text(command_text):
            return f" Launch blocked for {clean_name}: invalid command"

        tokens = command_text.split()
        executable = tokens[0]
        resolved_exec = shutil.which(executable)
        if not resolved_exec:
            return f" Application unavailable on this system: {clean_name}"

        args = [resolved_exec] + tokens[1:]
        if any(not self._is_safe_command_text(part) for part in args):
            return " Unsafe application name blocked"

        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
            return f" Opened {clean_name}"
        except Exception as exc:
            return f" Failed to open {clean_name}: {exc}"

    def list_installed_apps(self) -> str:
        if not self.installed_apps:
            return " No applications discovered"
        app_list = sorted(self.installed_apps.keys())
        lines = [f" Available Applications ({len(app_list)}):"]
        lines.extend([f"  • {app}" for app in app_list])
        lines.append("\n Try: 'open [app name]' to launch any app")
        return "\n".join(lines)
