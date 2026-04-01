"""Input and desktop interaction handlers."""

from __future__ import annotations

import os
import time
from datetime import datetime

from ..constants import KEY_COMBINATIONS


class InputHandler:
    def _get_pyautogui(self):
        try:
            import pyautogui
            return pyautogui
        except Exception:
            return None

    def type_text(self, text: str = "", delay_seconds: float = 2.0) -> str:
        pyautogui = self._get_pyautogui()
        if pyautogui is None:
            return " Desktop automation unavailable in this environment"
        clean = (text or "").strip()
        if not clean:
            return " Please provide text to type"
        time.sleep(max(0.0, float(delay_seconds)))
        pyautogui.write(clean, interval=0.05)
        return f" Typed: {clean}"

    def press_keys(self, keys: str = "") -> str:
        pyautogui = self._get_pyautogui()
        if pyautogui is None:
            return " Desktop automation unavailable in this environment"

        clean = (keys or "").strip().lower()
        if not clean:
            return " Please provide keys to press"

        if clean in KEY_COMBINATIONS:
            pyautogui.hotkey(*KEY_COMBINATIONS[clean])
            return f" Pressed: {keys}"

        pyautogui.press(clean)
        return f" Pressed key: {keys}"

    def take_screenshot(self) -> str:
        pyautogui = self._get_pyautogui()
        if pyautogui is None:
            return " Screenshot unavailable in this environment"

        filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        screenshot_dir = "Data"
        os.makedirs(screenshot_dir, exist_ok=True)
        filepath = os.path.join(screenshot_dir, filename)

        screenshot = pyautogui.screenshot()
        screenshot.save(filepath)
        return f" Screenshot saved: {filename}"
