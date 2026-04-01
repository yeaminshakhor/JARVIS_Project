# pyright: reportUndefinedVariable=false
import json
import logging
import os
import platform
import socket
import subprocess
import time
import functools
from datetime import datetime
from pathlib import Path
from typing import Tuple, Any, Dict, List

from .config import ConfigManager
from .paths import CACHE_DIR, CONVERSATIONS_DIR

try:
    from rich.console import Console
    from rich.table import Table
    _HAS_RICH = True
except Exception:
    Console = None
    Table = None
    _HAS_RICH = False


class _FallbackConsole:
    def print(self, *args, **kwargs):
        print(*args)


console = Console() if _HAS_RICH else _FallbackConsole()


def load_env_map(env_path: str = ".env") -> Dict[str, str]:
    return ConfigManager.env_map(env_path)


def env_get(*keys: str, default: str = "", env_map: Dict[str, str] = None) -> str:
    return ConfigManager.get(*keys, default=default, env_map=env_map)


def env_has(*keys: str, env_map: Dict[str, str] = None) -> bool:
    return bool(env_get(*keys, default="", env_map=env_map))


class EnhancedErrorHandler:
    @staticmethod
    def error_handler(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                logging.exception("Error in %s: %s", func.__name__, exc)
                raise

        return wrapper


class PerformanceTracker:
    @staticmethod
    def track_performance(operation_name):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logging.info("Performance: %s took %.3fs", operation_name, elapsed)
                return result

            return wrapper

        return decorator


class SecurityLayer:
    def __init__(self):
        self.restricted_commands = [
            "rm -rf", "format", "del /", "sudo", "su ", "passwd",
            "chmod 777", "dd if=", "mkfs", "fdisk"
        ]

    def validate_command(self, command: str) -> Tuple[bool, str]:
        lowered = command.lower()
        for restricted in self.restricted_commands:
            if restricted in lowered:
                return False, f" Security: Command contains restricted pattern '{restricted}'"

        if any(word in lowered for word in ["shutdown", "restart", "reboot"]):
            return True, "️ System command - use with caution"

        return True, "Command validated"


class EnhancedCache:
    def __init__(self, cache_dir: str | Path = CACHE_DIR, ttl_seconds: int = 3600):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    def _cache_path(self, key: str) -> Path:
        safe_key = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in key)[:120]
        return self.cache_dir / f"{safe_key}.json"

    def get_cached_result(self, key: str):
        path = self._cache_path(key)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as file:
                payload = json.load(file)
            if time.time() - payload.get("time", 0) > self.ttl_seconds:
                return None
            return payload.get("value")
        except Exception:
            return None

    def set_cached_result(self, key: str, value: Any):
        path = self._cache_path(key)
        payload = {"time": time.time(), "value": value}
        with open(path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False)


class CommandHistory:
    def __init__(self, history_file: str | Path = CONVERSATIONS_DIR / "command_history.json"):
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history = self._load_history()

    def _load_history(self) -> List[Dict[str, Any]]:
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def add_command(self, command: str, result: str, success: bool = True):
        self.history.append(
            {
                "time": datetime.now().isoformat(timespec="seconds"),
                "command": command,
                "result": result,
                "success": success,
            }
        )
        self.history = self.history[-500:]
        self.save_history()

    def save_history(self):
        with open(self.history_file, "w", encoding="utf-8") as file:
            json.dump(self.history, file, indent=2, ensure_ascii=False)

    def show_history_table(self):
        if not self.history:
            console.print("No command history.")
            return

        if _HAS_RICH:
            table = Table(title="Command History")
            table.add_column("Time", style="cyan")
            table.add_column("Success", style="green")
            table.add_column("Command", style="white")
            table.add_column("Result", style="yellow")
            for item in self.history[-20:]:
                table.add_row(
                    item.get("time", ""),
                    "" if item.get("success", False) else "",
                    str(item.get("command", "")),
                    str(item.get("result", ""))[:80],
                )
            console.print(table)
            return

        for item in self.history[-20:]:
            status = "OK" if item.get("success", False) else "FAIL"
            print(f"[{item.get('time', '')}] [{status}] {item.get('command', '')} -> {str(item.get('result', ''))[:80]}")


class AIProviderManager:
    def __init__(self):
        self.providers = {}

    def register_provider(self, name: str, provider: Any):
        self.providers[name] = provider

    def get_provider(self, name: str):
        return self.providers.get(name)


def safe_read(path: str, default: str = "") -> str:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as file:
                return file.read().strip()
    except Exception as exc:
        logging.error("Read failed: %s - %s", path, exc)
    return default


def load_json(path: str | Path, default: Any):
    target = Path(path)
    try:
        if target.exists():
            with open(target, "r", encoding="utf-8") as file:
                return json.load(file)
    except Exception as exc:
        logging.debug("JSON load failed: %s - %s", target, exc)
    return default


def save_json(path: str | Path, data: Any) -> bool:
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target.with_suffix(target.suffix + ".tmp")
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        os.replace(temp_path, target)
        return True
    except Exception as exc:
        logging.debug("JSON save failed: %s - %s", target, exc)
        return False


def safe_write(path: str, data: str) -> bool:
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            file.write(str(data))
        return True
    except Exception as exc:
        logging.error("Write failed: %s - %s", path, exc)
        return False


def sanitize_path(path: str) -> str:
    return os.path.abspath(os.path.normpath(path))


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except Exception:
        return "Unknown"


def color_lerp(c1, c2, t: float):
    t = max(0.0, min(1.0, t))
    try:
        from PyQt5.QtGui import QColor
        if hasattr(c1, "red") and hasattr(c2, "red"):
            return QColor(
                int(c1.red() + (c2.red() - c1.red()) * t),
                int(c1.green() + (c2.green() - c1.green()) * t),
                int(c1.blue() + (c2.blue() - c1.blue()) * t),
            )
    except Exception:
        pass

    if isinstance(c1, (tuple, list)) and isinstance(c2, (tuple, list)) and len(c1) >= 3 and len(c2) >= 3:
        return (
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t),
        )

    return c1


def _settings_path() -> str:
    root = Path(__file__).resolve().parent.parent
    settings_file = root / "Frontend" / "Files" / "jarvis_settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    return str(settings_file)


def load_settings() -> Dict[str, Any]:
    defaults = {
        "neon_color": "#00FFFF",
        "font_family": "Courier",
        "font_size": 10,
    }
    settings_file = _settings_path()
    try:
        if os.path.exists(settings_file):
            with open(settings_file, "r", encoding="utf-8") as file:
                loaded = json.load(file)
            if isinstance(loaded, dict):
                defaults.update(loaded)
    except Exception:
        logging.exception("Failed to load settings")
    return defaults


def save_settings(settings: Dict[str, Any]):
    settings_file = _settings_path()
    try:
        with open(settings_file, "w", encoding="utf-8") as file:
            json.dump(settings, file, indent=2, ensure_ascii=False)
    except Exception:
        logging.exception("Failed to save settings")


class NetworkBluetoothDetector:
    @staticmethod
    def get_wifi_info():
        try:
            if platform.system() == "Linux":
                result = subprocess.run(["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"], capture_output=True, text=True)
                if result.returncode == 0:
                    active = next((line for line in result.stdout.splitlines() if line.startswith("yes:")), None)
                    if active:
                        return f"Connected ({active.split(':', 1)[1]})", True
                return "Disconnected", False
            return "Unknown", False
        except Exception:
            return "Unknown", False

    @staticmethod
    def get_bluetooth_info():
        try:
            if platform.system() == "Linux":
                result = subprocess.run(["rfkill", "list", "bluetooth"], capture_output=True, text=True)
                text = result.stdout.lower()
                if "soft blocked: no" in text or "hard blocked: no" in text:
                    return "Available", True
                return "Unavailable", False
            return "Unknown", False
        except Exception:
            return "Unknown", False

    @staticmethod
    def get_local_ip():
        return get_local_ip()

    @staticmethod
    def get_available_wifi() -> List[str]:
        networks = []
        try:
            if platform.system() == "Linux":
                result = subprocess.run(["nmcli", "-t", "-f", "SSID", "dev", "wifi"], capture_output=True, text=True)
                if result.returncode == 0:
                    seen = set()
                    for line in result.stdout.splitlines():
                        ssid = line.strip()
                        if ssid and ssid not in seen:
                            seen.add(ssid)
                            networks.append(ssid)
        except Exception:
            pass
        return networks

    @staticmethod
    def get_available_bluetooth() -> List[str]:
        devices = []
        try:
            if platform.system() == "Linux":
                result = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True)
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        parts = line.split(" ", 2)
                        if len(parts) == 3:
                            devices.append(parts[2])
        except Exception:
            pass
        return devices

