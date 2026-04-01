"""System-level automation handlers."""

from __future__ import annotations

import platform
import subprocess

import psutil


class SystemHandler:
    def __init__(self, os_type: str):
        self.os_type = os_type

    def _set_bluetooth_power(self, enable: bool) -> str:
        try:
            if self.os_type == "linux":
                state = "unblock" if enable else "block"
                subprocess.run(["rfkill", state, "bluetooth"], check=False)
                return f" Bluetooth {'enabled' if enable else 'disabled'}"
            if self.os_type == "windows":
                return " Bluetooth power toggle is not automated on Windows"
            return " Bluetooth toggle not supported on this OS"
        except Exception as exc:
            return f" Bluetooth toggle error: {exc}"

    def bluetooth_on(self) -> str:
        return self._set_bluetooth_power(True)

    def bluetooth_off(self) -> str:
        return self._set_bluetooth_power(False)

    def get_bluetooth_info(self) -> str:
        try:
            if self.os_type == "linux":
                result = subprocess.run(["bluetoothctl", "show"], capture_output=True, text=True)
                if result.returncode == 0:
                    return " Bluetooth: Available\n Use 'open bluetooth' to open Bluetooth settings"
                return " Bluetooth: Not available or not installed"
            if self.os_type == "windows":
                return " Bluetooth: Use Windows Settings\n Try 'open settings'"
            return " Bluetooth info not available on this OS"
        except Exception as exc:
            return f" Bluetooth error: {exc}"

    def volume_up(self) -> str:
        try:
            if self.os_type == "linux":
                subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+10%"], check=False)
            else:
                try:
                    import pyautogui
                except Exception:
                    pyautogui = None
                if pyautogui is None:
                    return " Volume control unavailable in this environment"
                pyautogui.press("volumeup")
            return " Volume increased"
        except Exception as exc:
            return f" Volume control error: {exc}"

    def volume_down(self) -> str:
        try:
            if self.os_type == "linux":
                subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-10%"], check=False)
            else:
                try:
                    import pyautogui
                except Exception:
                    pyautogui = None
                if pyautogui is None:
                    return " Volume control unavailable in this environment"
                pyautogui.press("volumedown")
            return " Volume decreased"
        except Exception as exc:
            return f" Volume control error: {exc}"

    def mute_volume(self) -> str:
        try:
            if self.os_type == "linux":
                subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], check=False)
            else:
                try:
                    import pyautogui
                except Exception:
                    pyautogui = None
                if pyautogui is None:
                    return " Volume control unavailable in this environment"
                pyautogui.press("volumemute")
            return " Volume toggled"
        except Exception as exc:
            return f" Volume control error: {exc}"

    def system_shutdown(self) -> str:
        _ = self
        return " System shutdown is intentionally disabled for safety"

    def system_restart(self) -> str:
        _ = self
        return " System restart is intentionally disabled for safety"

    def get_system_info(self, app_count: int) -> str:
        info = []
        info.append(" SYSTEM INFORMATION")
        info.append(f"OS: {platform.system()} {platform.release()}")
        info.append(f"Architecture: {platform.machine()}")
        info.append(f"Python: {platform.python_version()}")
        info.append(f"Automation: {app_count} apps available")

        try:
            memory = psutil.virtual_memory()
            info.append(f"Memory: {memory.percent}% used ({memory.used//(1024**3)}GB/{memory.total//(1024**3)}GB)")
            cpu_percent = psutil.cpu_percent(interval=1)
            info.append(f"CPU: {cpu_percent}% used")
            disk = psutil.disk_usage("/")
            info.append(f"Disk: {disk.percent}% used ({disk.used//(1024**3)}GB/{disk.total//(1024**3)}GB)")
            battery = psutil.sensors_battery()
            if battery:
                info.append(f"Battery: {battery.percent}%")
        except Exception:
            info.append("Resource info: Limited")

        return "\n".join(info)
