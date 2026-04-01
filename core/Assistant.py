#!/usr/bin/env python3
"""Enhanced AI Automation System - layered architecture with compatibility facade."""

from __future__ import annotations

import asyncio
import logging
import platform
import time
from typing import Any, Dict, List

from .automation.constants import SUPPORTED_WEBSITES
from .automation.executor import CommandExecutor
from .automation.parser import HybridCommandParser
from .automation.registry import CommandRegistry
from .automation.security import AutomationSecurityPolicy
from .automation.brain import AIBrain as LocalAIBrain
from .automation.voice import VoiceEngine
from .automation.handlers import (
    ApplicationHandler,
    BrowserHandler,
    DeviceHandler,
    InputHandler,
    SystemHandler,
)
from .commands import load_all_commands
from .enhanced_compat import SecurityLayer
from .config import ConfigManager
from .paths import LOGS_DIR
from .memory.advanced_memory import AdvancedMemorySystem
from .ai_brain import AIBrain


class EnhancedProfessionalAIAutomation:
    """Compatibility facade around parser/registry/executor/handlers automation layers."""

    def __init__(self):
        self.os_type = platform.system().lower()
        self.security_layer = SecurityLayer()
        self.setup_logging()

        self.app_handler = ApplicationHandler(self.os_type)
        self.browser_handler = BrowserHandler()
        self.system_handler = SystemHandler(self.os_type)
        self.input_handler = InputHandler()
        self.device_handler = DeviceHandler()

        self.ai_brain = AIBrain(api_key=ConfigManager.get("OPENAI_API_KEY", default=""))
        self.brain = LocalAIBrain()
        self.voice = None
        self.memory = None

        self.parser = HybridCommandParser(
            app_names=list(self.app_handler.installed_apps.keys()),
            website_names=list(SUPPORTED_WEBSITES.keys()),
            llm_callable=lambda prompt: self.ai_brain.parse_command(prompt, self.registry.list_actions()),
        )
        self.registry = CommandRegistry()
        self.executor = CommandExecutor(self.registry)
        self.security_policy = AutomationSecurityPolicy(self.security_layer)
        self.current_role = "user"
        self.context = {
            "last_action": None,
            "last_target": None,
            "conversation": [],
        }
        self.observability = {
            "commands_total": 0,
            "commands_ok": 0,
            "commands_failed": 0,
            "last_action": None,
            "last_duration_ms": 0.0,
            "avg_duration_ms": 0.0,
            "last_error": "",
        }
        self.logs: List[str] = []
        self._loaded_plugins: List[str] = []

        self._loaded_plugins = load_all_commands(self.registry, self, self.logger)
        self.command_registry = self.registry.handlers()
        self.installed_apps = self.app_handler.installed_apps

        self.logger.info(
            "Enhanced AI Automation System initialized - %d apps discovered",
            len(self.installed_apps),
        )
        if self._loaded_plugins:
            self.logger.info("Loaded plugins: %s", ", ".join(self._loaded_plugins))

    def setup_logging(self):
        log_level = getattr(logging, ConfigManager.get("JARVIS_LOG_LEVEL", default="WARNING").upper(), logging.WARNING)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOGS_DIR / "automation.log"

        has_file = False
        has_stream = False
        for handler in self.logger.handlers:
            if isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", "") == str(log_path):
                has_file = True
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                has_stream = True

        if not has_file:
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        if not has_stream:
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            self.logger.addHandler(stream_handler)

        self.logger.propagate = False

    def _register_commands(self):
        # Backward-compatible entrypoint for callers that still invoke manual registration.
        self._loaded_plugins = load_all_commands(self.registry, self, self.logger)

    def _classify_ai_intent(self, command: str) -> Dict[str, Any]:
        try:
            from .model import classify_with_confidence

            raw = classify_with_confidence(command)
            intent = str(raw.get("intent", "")).strip().lower()
            query = str(raw.get("query", "")).strip()
            return self._map_intent_to_action(intent, query, raw)
        except Exception:
            return {"action": "", "confidence": 0.0}

    def _map_intent_to_action(self, intent: str, query: str, raw: Dict[str, Any]) -> Dict[str, Any]:
        action_map = {
            "open": "open_app",
            "website": "open_website",
            "search": "search_web",
            "system": "system_info",
        }
        action = action_map.get(intent, "")
        payload: Dict[str, Any] = {
            "action": action,
            "confidence": raw.get("confidence", 0.0),
        }

        if action == "open_app" and query:
            payload["app_name"] = query.lower()
        elif action == "open_website" and query:
            payload["website"] = query.lower()
        elif action == "search_web" and query:
            payload["query"] = query

        return payload

    def _update_context(self, user_input: str, action: str, params: Dict[str, str]) -> None:
        self.context["last_action"] = action
        self.context["last_target"] = (
            params.get("app_name")
            or params.get("website")
            or params.get("query")
            or params.get("url")
            or ""
        )
        conversation = self.context.get("conversation", [])
        if isinstance(conversation, list):
            conversation.append({"user": user_input, "action": action})
            self.context["conversation"] = conversation[-20:]

    def _record_observability(self, action: str, duration_ms: float, success: bool, error: str = "") -> None:
        total = int(self.observability.get("commands_total", 0)) + 1
        ok = int(self.observability.get("commands_ok", 0)) + (1 if success else 0)
        failed = int(self.observability.get("commands_failed", 0)) + (0 if success else 1)
        prev_avg = float(self.observability.get("avg_duration_ms", 0.0))
        self.observability["commands_total"] = total
        self.observability["commands_ok"] = ok
        self.observability["commands_failed"] = failed
        self.observability["last_action"] = action
        self.observability["last_duration_ms"] = round(duration_ms, 2)
        self.observability["avg_duration_ms"] = round(((prev_avg * (total - 1)) + duration_ms) / max(total, 1), 2)
        self.observability["last_error"] = error

    def _append_log(self, line: str) -> None:
        entry = str(line or "").strip()
        if not entry:
            return
        self.logs.append(entry)
        if len(self.logs) > 500:
            self.logs = self.logs[-500:]

    def _ai_fallback(self, text: str) -> str:
        return str(self.ai_brain.general_chat(text))

    def _get_memory(self) -> AdvancedMemorySystem:
        if self.memory is None:
            self.memory = AdvancedMemorySystem()
        return self.memory

    def _get_voice(self) -> VoiceEngine:
        if self.voice is None:
            self.voice = VoiceEngine()
        return self.voice

    def safe_execute(self, action, params):
        try:
            return self.execute_command(action, **params)
        except Exception as exc:
            return f"Execution error: {exc}"

    def format_response(self, text):
        return str(text).strip()

    # Browser handlers
    def open_browser(self, url: str = ""):
        return self.browser_handler.open_browser(url)

    def open_website(self, website: str = ""):
        return self.browser_handler.open_website(website)

    def search_web(self, query: str = ""):
        return self.browser_handler.search_web(query)

    # App handlers
    def open_application(self, app_name: str = ""):
        return self.app_handler.open_application(app_name)

    def list_installed_apps(self):
        return self.app_handler.list_installed_apps()

    # System handlers
    def get_system_info(self):
        return self.system_handler.get_system_info(app_count=len(self.installed_apps))

    def get_bluetooth_info(self):
        return self.system_handler.get_bluetooth_info()

    def bluetooth_on(self):
        return self.system_handler.bluetooth_on()

    def bluetooth_off(self):
        return self.system_handler.bluetooth_off()

    def volume_up(self):
        return self.system_handler.volume_up()

    def volume_down(self):
        return self.system_handler.volume_down()

    def mute_volume(self):
        return self.system_handler.mute_volume()

    def system_shutdown(self):
        return self.system_handler.system_shutdown()

    def system_restart(self):
        return self.system_handler.system_restart()

    # Input/device handlers
    def type_text(self, text: str = ""):
        return self.input_handler.type_text(text)

    def press_keys(self, keys: str = ""):
        return self.input_handler.press_keys(keys)

    def take_screenshot(self):
        return self.input_handler.take_screenshot()

    def take_photo(self):
        return self.device_handler.take_photo()

    def remember_value(self, payload: str = "", key: str = "", value: str = ""):
        if key and value:
            return self.memory.remember(str(key).strip(), str(value).strip())

        raw = str(payload or "").strip()
        if "=" not in raw:
            return "Usage: remember <key> = <value>"
        left, right = raw.split("=", 1)
        return self.memory.remember(left.strip(), right.strip())

    def recall_value(self, key: str = "", payload: str = ""):
        clean = str(key or payload or "").strip()
        if not clean:
            return "Usage: recall <key>"
        return self.memory.recall(clean)

    # Parser/executor/security
    def _commands_from_parsed(self, parsed: Any) -> List[Dict[str, str]]:
        if isinstance(parsed, list):
            return [cmd for cmd in parsed if isinstance(cmd, dict)]
        if isinstance(parsed, dict):
            return [parsed]
        return []

    def parse_natural_command(self, command: str) -> List[Dict[str, str]]:
        ai_intent = self._classify_ai_intent(command)
        parsed = self.parser.parse_with_ai(command, ai_intent)
        self.logger.info("Parsed command(s): %r -> %s", command, parsed)
        return parsed

    def set_role(self, role: str) -> str:
        normalized = (role or "").strip().lower()
        if normalized not in {"user", "admin"}:
            return "Invalid role. Use 'user' or 'admin'"
        self.current_role = normalized
        return f"Role set to {normalized}"

    def execute_command(self, action: str, **kwargs):
        start = time.perf_counter()
        spec = self.registry.get(action)
        permission = spec.permission if spec else "basic"
        allowed, msg = self.security_policy.validate_action(
            action,
            kwargs,
            permission=permission,
            role=self.current_role,
        )
        if not allowed:
            duration_ms = (time.perf_counter() - start) * 1000.0
            self._record_observability(action, duration_ms, success=False, error=msg)
            return msg
        try:
            result = self.executor.execute(action, **kwargs)
            self.logger.info("Automation command executed: %s", action)
            duration_ms = (time.perf_counter() - start) * 1000.0
            self._record_observability(action, duration_ms, success=True)
            return result
        except Exception as exc:
            self.logger.exception("Automation command failed: %s", action)
            duration_ms = (time.perf_counter() - start) * 1000.0
            self._record_observability(action, duration_ms, success=False, error=str(exc))
            return f" Command failed: {exc}"

    async def execute_command_async(self, action: str, **kwargs):
        spec = self.registry.get(action)
        permission = spec.permission if spec else "basic"
        allowed, msg = self.security_policy.validate_action(
            action,
            kwargs,
            permission=permission,
            role=self.current_role,
        )
        if not allowed:
            self._record_observability(action, 0.0, success=False, error=msg)
            return msg

        start = time.perf_counter()
        try:
            result = await self.executor.execute_async(action, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000.0
            self._record_observability(action, duration_ms, success=True)
            self.logger.info("Automation command executed async: %s", action)
            return result
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000.0
            self._record_observability(action, duration_ms, success=False, error=str(exc))
            self.logger.exception("Automation command async failed: %s", action)
            return f" Command failed: {exc}"

    def process_command(self, user_input: str):
        clean = (user_input or "").strip()
        if not clean:
            return "Please enter a command."

        memory = self._get_memory()
        memory.add_context(clean)

        is_valid, security_msg = self.security_policy.validate_raw(clean)
        if not is_valid:
            return self.format_response(security_msg)

        # Step 1: Try parser
        parsed_raw = self.parse_natural_command(clean)
        parsed = parsed_raw[0] if isinstance(parsed_raw, list) and parsed_raw else (
            parsed_raw if isinstance(parsed_raw, dict) else {"action": "unknown", "command": clean}
        )

        # Step 2: If parser fails -> use AI brain
        if parsed.get("action") == "unknown":
            parsed = self.brain.analyze(clean)
            self.logger.info("AI Brain used for: %s -> %s", clean, parsed)

        action = parsed.get("action", "unknown")

        if action == "unknown":
            return self.format_response(f"I don't understand: '{clean}'")

        params = {k: v for k, v in parsed.items() if k != "action"}
        result = self.safe_execute(action, params)
        memory.add_context(str(result))
        return self.format_response(result)

    def start_voice_mode(self):
        voice = self._get_voice()
        voice.speak("Voice mode activated")

        while True:
            command = voice.listen()

            if not command:
                continue

            lowered = command.lower()
            if "exit" in lowered or "stop" in lowered:
                voice.speak("Shutting down voice mode")
                break

            response = self.process_command(command)
            voice.speak(f"Done: {response}")

    async def process_command_async(self, user_input: str):
        clean = (user_input or "").strip()
        if not clean:
            return " Please enter a command."

        memory = self._get_memory()
        memory.add_context(clean)

        self._append_log(f"> {clean}")

        is_valid, security_msg = self.security_policy.validate_raw(clean)
        if not is_valid:
            self._append_log(str(security_msg))
            return security_msg

        parsed = self.parse_natural_command(clean)
        commands = self._commands_from_parsed(parsed)
        results: List[str] = []

        for cmd in commands:
            action = cmd.get("action", "unknown")
            params = {k: v for k, v in cmd.items() if k != "action"}

            if action == "unknown":
                unknown_text = str(params.get("command", clean)).strip()
                results.append(self._ai_fallback(unknown_text))
                continue

            self._update_context(clean, action, params)
            result = await self.execute_command_async(action, **params)
            results.append(str(result))

        final_result = "\n".join(results)
        self._append_log(final_result)
        return final_result

    def get_observability_snapshot(self) -> Dict[str, Any]:
        return dict(self.observability)
