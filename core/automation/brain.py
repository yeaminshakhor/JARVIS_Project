from __future__ import annotations

from typing import Dict
import re


class AIBrain:
    """
    Intelligent decision layer for automation system.
    Works when parser is uncertain or command is complex.
    """

    def __init__(self):
        self.intent_map = {
            "open": "open_app",
            "launch": "open_app",
            "start": "open_app",
            "run": "open_app",
            "search": "search_web",
            "find": "search_web",
            "google": "search_web",
            "website": "open_website",
            "browser": "open_browser",
            "shutdown": "shutdown",
            "restart": "restart",
            "volume": "volume_up",
            "mute": "mute",
            "bluetooth": "bluetooth_on",
        }

    def analyze(self, text: str) -> Dict[str, str]:
        """
        Main AI logic to understand user intent.
        """
        text = (text or "").lower().strip()

        for keyword, action in self.intent_map.items():
            if keyword in text:
                return self._build_action(action, text)

        if "youtube" in text:
            return {"action": "open_website", "website": "youtube"}

        if "music" in text:
            return {"action": "search_web", "query": text}

        return {"action": "unknown", "command": text}

    def _build_action(self, action: str, text: str) -> Dict[str, str]:
        """
        Build structured command from detected intent.
        """
        if action == "open_app":
            name = re.sub(r"(open|launch|start|run)", "", text).strip()
            return {"action": "open_app", "app_name": name}

        if action == "search_web":
            query = re.sub(r"(search|find|google)", "", text).strip()
            return {"action": "search_web", "query": query}

        if action == "open_website":
            website = re.sub(r"(open|website|visit)", "", text).strip() or text
            return {"action": "open_website", "website": website}

        return {"action": action}
