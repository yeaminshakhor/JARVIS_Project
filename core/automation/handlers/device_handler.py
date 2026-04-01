"""Device-level handlers such as camera capture."""

from __future__ import annotations

import os
import time
from datetime import datetime


class DeviceHandler:
    def take_photo(self, delay_seconds: float = 1.0) -> str:
        try:
            import cv2
        except Exception as exc:
            return f" Camera error: {exc}"

        filename = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        photo_dir = "Data"
        os.makedirs(photo_dir, exist_ok=True)
        filepath = os.path.join(photo_dir, filename)

        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            return " Camera not accessible"

        try:
            time.sleep(max(0.0, float(delay_seconds)))
            ok, frame = camera.read()
            if ok:
                cv2.imwrite(filepath, frame)
                return f" Photo taken: {filename}"
            return " Failed to capture photo"
        finally:
            camera.release()
