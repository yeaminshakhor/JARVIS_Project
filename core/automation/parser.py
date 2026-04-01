"""Natural language command parser for automation."""

from __future__ import annotations

import re
from typing import Any, Dict, List


class GPTIntentEngine:
    """Lightweight fallback intent engine.

    This currently uses deterministic mock rules and is designed as a drop-in
    extension point for a real LLM call later.
    """

    def infer(self, text: str) -> Dict[str, str]:
        phrase = (text or "").strip().lower()
        if not phrase:
            return {"action": "unknown"}

        if "youtube" in phrase:
            return {"action": "open_website", "website": "youtube"}
        if "music" in phrase or "relaxing" in phrase:
            return {"action": "open_app", "app_name": "spotify"}
        if "status" in phrase or "system" in phrase:
            return {"action": "system_info"}

        return {"action": "unknown"}


class AdvancedCommandParser:
    def __init__(
        self,
        app_names: List[str] | None = None,
        website_names: List[str] | None = None,
        llm_callable: Any | None = None,
    ):
        self.app_names = [a.lower().strip() for a in (app_names or []) if a]
        self.website_names = [w.lower().strip() for w in (website_names or []) if w]
        self.llm_callable = llm_callable
        self.context = {
            "last_app": None,
            "last_query": None,
            "last_action": None,
        }
        self.ai_engine = GPTIntentEngine()
        self.intent_keywords = {
            "open_app": ["open", "launch", "start", "run"],
            "search_web": ["search", "google", "find"],
            "open_website": ["visit", "open website"],
            "open_browser": ["open browser", "browser"],
            "system_info": ["system info", "status"],
            "shutdown": ["shutdown", "power off"],
            "restart": ["restart", "reboot"],
            "volume_up": ["volume up", "increase volume"],
            "volume_down": ["volume down", "خفض الصوت"],
            "mute": ["mute", "silence"],
            "list_apps": ["list apps"],
            "bluetooth_info": ["bluetooth info"],
            "bluetooth_on": ["turn on bluetooth", "bluetooth on"],
            "bluetooth_off": ["turn off bluetooth", "bluetooth off"],
            "take_screenshot": ["screenshot", "capture screen"],
            "take_photo": ["photo", "picture"],
            "type_text": ["type"],
            "press_keys": ["press"],
            "remember": ["remember"],
            "recall": ["recall"],
        }

    def normalize_input(self, text: str) -> str:
        normalized = (text or "").strip().lower()
        normalized = re.sub(r"\b(hey jarvis|jarvis|please|can you|could you|would you)\b", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip(" ,")

    def split_commands(self, text: str) -> List[str]:
        separators = r"\band\b|\bthen\b|,|\&"
        parts = re.split(separators, text, flags=re.IGNORECASE)
        return [part.strip() for part in parts if part.strip()]

    def detect_intent(self, command: str) -> Dict[str, str]:
        cmd = (command or "").strip().lower()
        if not cmd:
            return {"action": "unknown", "command": ""}

        # Direct context recall phrases.
        if re.search(r"\b(again|it)\b", cmd):
            if self.context.get("last_action") == "open_app" or self.context.get("last_app"):
                return {"action": "open_app", "app_name": str(self.context.get("last_app") or "").strip()}
            if self.context.get("last_action") == "search_web" or self.context.get("last_query"):
                return {"action": "search_web", "query": str(self.context.get("last_query") or "").strip()}

        # Known website target handling.
        if self.website_names:
            if cmd.startswith("open ") or cmd.startswith("visit "):
                target = re.sub(r"^(open|visit)\s+", "", cmd).strip()
                if target in self.website_names:
                    return {"action": "open_website", "website": target}

        for intent, keywords in self.intent_keywords.items():
            for keyword in keywords:
                if keyword in cmd:
                    return self.extract_parameters(intent, cmd)

        return {"action": "unknown", "command": command.strip()}

    def extract_parameters(self, intent: str, command: str) -> Dict[str, str]:
        if intent == "open_app":
            app = re.sub(r"\b(open|launch|start|run)\b", "", command).strip()
            if app and app not in {"website", "browser"}:
                self.context["last_app"] = app
            return {"action": "open_app", "app_name": app}

        if intent == "search_web":
            query = re.sub(r"\b(search|google|find)\b", "", command).strip()
            if query:
                self.context["last_query"] = query
            return {"action": "search_web", "query": query}

        if intent == "open_website":
            website = re.sub(r"\b(visit|open website|open)\b", "", command).strip()
            return {"action": "open_website", "website": website or command.strip()}

        if intent == "open_browser":
            url = re.sub(r"\b(open browser|browser|open)\b", "", command).strip()
            return {"action": "open_browser", "url": url}

        if intent == "type_text":
            text = re.sub(r"\btype\b", "", command).strip()
            return {"action": "type_text", "text": text}

        if intent == "press_keys":
            keys = re.sub(r"\bpress\b", "", command).strip()
            return {"action": "press_keys", "keys": keys}

        if intent == "remember":
            payload = re.sub(r"\bremember\b", "", command).strip()
            return {"action": "remember", "payload": payload}

        if intent == "recall":
            key = re.sub(r"\brecall\b", "", command).strip()
            return {"action": "recall", "key": key}

        return {"action": intent}

    def apply_context(self, parsed: Dict[str, str]) -> Dict[str, str]:
        action = parsed.get("action", "unknown")

        if action == "open_app" and not (parsed.get("app_name") or "").strip():
            parsed["app_name"] = str(self.context.get("last_app") or "")

        if action == "search_web" and not (parsed.get("query") or "").strip():
            parsed["query"] = str(self.context.get("last_query") or "")

        return parsed

    def parse(self, text: str) -> List[Dict[str, str]]:
        normalized = self.normalize_input(text)
        if not normalized:
            return [{"action": "unknown", "command": ""}]

        commands = self.split_commands(normalized)
        if not commands:
            return [{"action": "unknown", "command": normalized}]

        results: List[Dict[str, str]] = []
        for cmd in commands:
            parsed = self.detect_intent(cmd)
            # AI fallback for commands not covered by fast rule parser.
            if parsed.get("action") == "unknown":
                if callable(self.llm_callable):
                    try:
                        llm_actions = list(self.intent_keywords.keys()) + ["unknown"]
                        try:
                            llm_parsed = self.llm_callable(cmd)
                        except TypeError:
                            llm_parsed = self.llm_callable(cmd, llm_actions)
                        if isinstance(llm_parsed, dict) and llm_parsed.get("action"):
                            parsed = {k: str(v) for k, v in llm_parsed.items() if v is not None}
                    except Exception:
                        pass

            if parsed.get("action") == "unknown":
                inferred = self.ai_engine.infer(cmd)
                if isinstance(inferred, dict) and inferred.get("action"):
                    parsed = inferred
                    if parsed.get("action") == "unknown" and not parsed.get("command"):
                        parsed["command"] = cmd
            parsed = self.apply_context(parsed)
            self.context["last_action"] = parsed.get("action")
            results.append(parsed)
        return results

    def parse_with_ai(self, command: str, ai_intent: Dict[str, Any] | None) -> List[Dict[str, str]]:
        """Blend AI intent hints with rule-based parsing for safer command extraction."""
        parsed_commands = self.parse(command)
        intent = ai_intent or {}

        action = str(intent.get("action", "")).strip().lower()
        confidence_raw = intent.get("confidence", 0.0)
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.0

        if not action or confidence < 0.55:
            return parsed_commands

        for item in parsed_commands:
            if item.get("action") != "unknown":
                continue

            payload: Dict[str, str] = {"action": action}
            for key in ("query", "website", "url", "app_name", "text", "keys"):
                value = intent.get(key)
                if isinstance(value, str) and value.strip():
                    payload[key] = value.strip()
            item.update(payload)
            item.pop("command", None)
            break

        return parsed_commands


class SmartCommandParser(AdvancedCommandParser):
    """Compatibility alias while parser is being upgraded."""


class CommandParser(AdvancedCommandParser):
    """Backward-compatible alias for legacy imports."""


class HybridCommandParser(AdvancedCommandParser):
    """Compatibility alias for hybrid parser naming."""
