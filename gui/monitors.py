"""
System Monitors for JARVIS GUI
Displays CPU, Memory, and Battery status with visual indicators.
"""

import json
import logging
import os
import threading
import time

import psutil
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QHBoxLayout, QWidget

from core.utils import color_lerp

# Configuration
CURRENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_DIR = os.path.join(CURRENT_DIR, "Frontend", "Files")
SETTINGS_FILE = os.path.join(TEMP_DIR, "jarvis_settings.json")


def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"neon_color": "#00FFFF", "font_family": "Courier", "font_size": 10}


SETTINGS = load_settings()


class _SystemStatsCache:
    """Collect system stats once per second on a background thread."""

    def __init__(self):
        self._lock = threading.Lock()
        self._snapshot = {
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "memory_used": 0,
            "memory_total": 0,
            "battery_percent": 0.0,
            "battery_charging": False,
            "has_battery": False,
            "timestamp": time.time(),
        }
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            # Prime cpu_percent so subsequent calls are meaningful.
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

        while not self._stop_event.is_set():
            try:
                cpu_percent = float(psutil.cpu_percent(interval=1.0))
                mem = psutil.virtual_memory()
                battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None

                with self._lock:
                    self._snapshot = {
                        "cpu_percent": cpu_percent,
                        "memory_percent": float(getattr(mem, "percent", 0.0)),
                        "memory_used": int(getattr(mem, "used", 0)),
                        "memory_total": int(getattr(mem, "total", 0)),
                        "battery_percent": float(getattr(battery, "percent", 0.0)) if battery else 0.0,
                        "battery_charging": bool(getattr(battery, "power_plugged", False)) if battery else False,
                        "has_battery": battery is not None,
                        "timestamp": time.time(),
                    }
            except Exception:
                logging.exception("System stats cache update failed")
                self._stop_event.wait(1.0)

    def stop(self):
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass

    def get(self):
        with self._lock:
            return dict(self._snapshot)


_STATS_CACHE = _SystemStatsCache()


def get_system_stats_snapshot():
    return _STATS_CACHE.get()


class _CachedMonitor(QWidget):
    """Base monitor that redraws to an internal pixmap only when values change."""

    def __init__(self, parent=None, refresh_ms=1000):
        super().__init__(parent)
        self._cached_pixmap = QPixmap()
        self._last_value = None
        self._render_delta = 0.5
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.update_stats)
        self._refresh_timer.start(refresh_ms)

    def resizeEvent(self, event):
        self._cached_pixmap = QPixmap()
        super().resizeEvent(event)

    def update_stats(self):
        value = self._value_for_cache_key(get_system_stats_snapshot())
        if self._value_changed(value):
            self._last_value = value
            self._cached_pixmap = QPixmap()
            self.update()

    def _value_for_cache_key(self, _snapshot):
        raise NotImplementedError

    def _draw_monitor(self, painter: QPainter, snapshot: dict):
        raise NotImplementedError

    def _value_changed(self, value):
        if self._last_value is None:
            return True

        if isinstance(value, tuple) and isinstance(self._last_value, tuple):
            if len(value) != len(self._last_value):
                return True
            for idx, current in enumerate(value):
                previous = self._last_value[idx]
                if isinstance(current, (int, float)) and isinstance(previous, (int, float)):
                    if abs(float(current) - float(previous)) >= self._render_delta:
                        return True
                elif current != previous:
                    return True
            return False

        if isinstance(value, (int, float)) and isinstance(self._last_value, (int, float)):
            return abs(float(value) - float(self._last_value)) >= self._render_delta

        return value != self._last_value

    def paintEvent(self, _event):
        if self._cached_pixmap.size() != self.size() or self._cached_pixmap.isNull():
            self._cached_pixmap = QPixmap(self.size())
            self._cached_pixmap.fill(Qt.transparent)
            painter = QPainter(self._cached_pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            self._draw_monitor(painter, get_system_stats_snapshot())
            painter.end()

        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._cached_pixmap)


class LargeCPUMonitor(_CachedMonitor):
    """CPU usage monitor with visual gauge."""

    def __init__(self, parent=None):
        super().__init__(parent=parent, refresh_ms=1000)
        self.setFixedSize(320, 150)
        self.update_stats()

    def _value_for_cache_key(self, snapshot):
        return float(snapshot.get("cpu_percent", 0.0))

    def _draw_monitor(self, painter: QPainter, snapshot: dict):
        cpu_percent = float(snapshot.get("cpu_percent", 0.0))

        painter.fillRect(self.rect(), QColor(0, 10, 10))

        painter.setPen(QColor(SETTINGS["neon_color"]))
        painter.setFont(QFont(SETTINGS["font_family"], 16, QFont.Bold))
        painter.drawText(10, 30, " CPU USAGE")

        painter.setFont(QFont(SETTINGS["font_family"], 36, QFont.Bold))
        painter.drawText(100, 90, f"{cpu_percent:.1f}%")

        bar_width = 280
        bar_height = 25
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(50, 50, 50))
        painter.drawRoundedRect(10, 100, bar_width, bar_height, 10, 10)

        fill_width = int(bar_width * (cpu_percent / 100.0))
        fill_color = color_lerp(QColor("#00FF00"), QColor("#FF0000"), cpu_percent / 100.0)
        painter.setBrush(fill_color)
        painter.drawRoundedRect(10, 100, fill_width, bar_height, 10, 10)


class LargeMemoryMonitor(_CachedMonitor):
    """Memory usage monitor with visual gauge and details."""

    def __init__(self, parent=None):
        super().__init__(parent=parent, refresh_ms=1000)
        self.setFixedSize(320, 150)
        self.update_stats()

    def _value_for_cache_key(self, snapshot):
        return (
            float(snapshot.get("memory_percent", 0.0)),
            int(snapshot.get("memory_used", 0)),
            int(snapshot.get("memory_total", 0)),
        )

    def _draw_monitor(self, painter: QPainter, snapshot: dict):
        mem_percent = float(snapshot.get("memory_percent", 0.0))
        used = int(snapshot.get("memory_used", 0))
        total = int(snapshot.get("memory_total", 0))

        painter.fillRect(self.rect(), QColor(0, 10, 10))

        painter.setPen(QColor(SETTINGS["neon_color"]))
        painter.setFont(QFont(SETTINGS["font_family"], 16, QFont.Bold))
        painter.drawText(10, 30, " MEMORY USAGE")

        painter.setFont(QFont(SETTINGS["font_family"], 36, QFont.Bold))
        painter.drawText(100, 90, f"{mem_percent:.1f}%")

        bar_width = 280
        bar_height = 25
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(50, 50, 50))
        painter.drawRoundedRect(10, 100, bar_width, bar_height, 10, 10)

        fill_width = int(bar_width * (mem_percent / 100.0))
        fill_color = color_lerp(QColor("#00FF00"), QColor("#FF0000"), mem_percent / 100.0)
        painter.setBrush(fill_color)
        painter.drawRoundedRect(10, 100, fill_width, bar_height, 10, 10)

        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont(SETTINGS["font_family"], 12))
        used_gb = used / float(1024**3) if used else 0.0
        total_gb = total / float(1024**3) if total else 0.0
        painter.drawText(10, 140, f"Used: {used_gb:.1f} GB / {total_gb:.1f} GB")


class LargeBatteryMonitor(_CachedMonitor):
    """Battery status monitor with visual battery icon."""

    def __init__(self, parent=None):
        super().__init__(parent=parent, refresh_ms=1000)
        self.setFixedSize(320, 150)
        self.update_stats()

    def _value_for_cache_key(self, snapshot):
        return (
            bool(snapshot.get("has_battery", False)),
            float(snapshot.get("battery_percent", 0.0)),
            bool(snapshot.get("battery_charging", False)),
        )

    def _draw_monitor(self, painter: QPainter, snapshot: dict):
        has_battery = bool(snapshot.get("has_battery", False))
        percent = float(snapshot.get("battery_percent", 0.0))
        charging = bool(snapshot.get("battery_charging", False))

        painter.fillRect(self.rect(), QColor(0, 10, 10))

        if not has_battery:
            painter.setPen(QColor(SETTINGS["neon_color"]))
            painter.setFont(QFont(SETTINGS["font_family"], 16, QFont.Bold))
            painter.drawText(self.rect(), Qt.AlignCenter, " NO BATTERY")
            return

        x, y = 60, 40
        battery_width, battery_height = 200, 80

        painter.setPen(QPen(QColor(SETTINGS["neon_color"]), 3))
        painter.drawRoundedRect(x, y, battery_width, battery_height, 15, 15)
        painter.drawRect(x + battery_width, y + 25, 15, 30)

        fill_width = int((battery_width - 6) * (percent / 100.0))
        fill_color = QColor("#00FF00") if charging else color_lerp(QColor("#FF0000"), QColor("#FFFF00"), percent / 100.0)
        painter.setBrush(fill_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(x + 3, y + 3, fill_width, battery_height - 6, 12, 12)

        painter.setPen(QColor(SETTINGS["neon_color"]))
        painter.setFont(QFont(SETTINGS["font_family"], 24, QFont.Bold))
        status = "CHARGING" if charging else f"{percent:.0f}%"
        painter.drawText(x, y + battery_height + 30, f" BATTERY: {status}")


class SimpleCPUMonitor(LargeCPUMonitor):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(220, 110)


class SimpleMemoryMonitor(LargeMemoryMonitor):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(220, 110)


class SimpleBatteryMonitor(LargeBatteryMonitor):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(220, 110)


class SystemMonitor(QWidget):
    """Compatibility monitor widget that aggregates simple monitors."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(700, 130)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(SimpleCPUMonitor(self))
        layout.addWidget(SimpleMemoryMonitor(self))
        layout.addWidget(SimpleBatteryMonitor(self))
