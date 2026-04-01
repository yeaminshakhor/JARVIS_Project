import json
import io
import importlib
import os
import re
import shutil
import subprocess
import unicodedata
import webbrowser
import logging
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import requests

from .exceptions import JarvisError
from .config import ConfigManager
from .validation import validate_url, validate_path_in_base
from .paths import CACHE_DIR, CONVERSATIONS_DIR, LOGS_DIR
from .utils import load_json, save_json
from .commands import (
    SUPPORTED_SOCIAL_PLATFORMS,
    ContactService,
    TaskService,
    MemoryService,
    MessagingService,
)


class SafeControlAssistant:
    """Safe assistant with practical controls and phased capabilities."""

    PARSER_VERSION = "2026.02.28-7"

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.download_dir = Path.home() / "Downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.data_root = CONVERSATIONS_DIR
        self.data_root.mkdir(parents=True, exist_ok=True)

        self.contacts_file = self.data_root / "contacts.json"
        self.tasks_file = self.data_root / "tasks.json"
        self.memory_file = self.data_root / "memory.json"
        self.chat_history_file = self.data_root / "chat_history.json"
        self.audit_log_file = LOGS_DIR / "command_audit.jsonl"
        self.research_dir = self.data_root / "research"
        self.research_dir.mkdir(parents=True, exist_ok=True)
        self.audit_log_file.parent.mkdir(parents=True, exist_ok=True)

        self.contacts = self._load_json(self.contacts_file, {})
        self.tasks = self._load_json(self.tasks_file, [])
        self.memory = self._load_json(self.memory_file, {})
        self.chat_history = self._load_json(self.chat_history_file, [])
        self.max_chat_history = 40
        self.last_media_query = None
        self._chatbot_checked = False
        self._chatbot_fn = None
        self._executor_checked = False
        self._executor = None
        self._auth_checked = False
        self._auth_cls = None

        self.blocked_patterns = [
            "rm -rf", "shutdown", "reboot", "poweroff", "format", "delete system32", "mkfs",
        ]
        self.supported_social_platforms = set(SUPPORTED_SOCIAL_PLATFORMS)
        self._platform_pattern = "|".join(sorted(self.supported_social_platforms))

        self.contact_service = ContactService(self.contacts, lambda: self._save_json(self.contacts_file, self.contacts))
        self.task_service = TaskService(self.tasks, lambda: self._save_json(self.tasks_file, self.tasks))
        self.memory_service = MemoryService(self.memory, lambda: self._save_json(self.memory_file, self.memory))
        self.messaging_service = MessagingService(self._resolve_contact_handle, self._looks_like_phone)

    def _load_json(self, path: Path, default):
        return load_json(path, default)

    def _save_json(self, path: Path, data):
        if not save_json(path, data):
            self.logger.debug("Failed to save JSON to %s", path)

    def _require_config(self, config: dict, keys, *, channel_name: str, enable_key_hint: str = ""):
        if not config.get("enabled"):
            hint = f" Set {enable_key_hint}=true in .env" if enable_key_hint else ""
            return False, f"{channel_name} channel is disabled.{hint}"
        missing = [key for key in keys if not config.get(key)]
        if missing:
            return False, f"{channel_name} not configured. Missing: {', '.join(missing)}"
        return True, "ok"

    def _lazy_import(self, checked_attr: str, value_attr: str, module_path: str, class_name: str):
        if not getattr(self, checked_attr):
            setattr(self, checked_attr, True)
            try:
                module = importlib.import_module(module_path)
                setattr(self, value_attr, getattr(module, class_name))
            except Exception as exc:
                self.logger.debug("Lazy import failed for %s.%s: %s", module_path, class_name, exc)
                setattr(self, value_attr, None)
        return getattr(self, value_attr)

    def help_text(self) -> str:
        return (
            "Commands\n"
            "General\n"
            "- hi / hello\n"
            "- open browser\n"
            "- open <facebook|instagram|whatsapp|youtube|gmail|drive>\n"
            "- open <photoshop|gimp|terminal|vlc|spotify|steam|epic|chrome|firefox|audio>\n"
            "- open settings\n"
            "- open files\n"
            "- open website <url or name>\n"
            "- youtube search <query>\n"
            "- search <query> on youtube\n"
            "- play music <song name>\n"
            "- search videos <query>\n"
            "- download file <url> [to <filename>]\n"
            "- download video <url or query>\n"
            "- wifi on|off\n"
            "- turn on/off wifi\n"
            "- bluetooth on|off\n"
            "- turn on/off bluetooth\n"
            "\n"
            "Phase 2 (communications)\n"
            "- add contact <name> on <platform> <handle>\n"
            "- list contacts\n"
            "- send message <platform> <person> [message]\n"
            "- send message to <person> on <platform> [saying <message>]\n"
            "- send whatsapp to +1234567890 saying <message>\n"
            "- send facebook to <user_id> saying <message>\n"
            "- send email to <email> subject <optional> saying <message>\n"
            "- check email / check my email\n"
            "- audio call <person> on <platform>\n"
            "- video call <person> on <platform>\n"
            "\n"
            "Phase 3 (research)\n"
            "- research <topic>\n"
            "- research papers <topic>\n"
            "\n"
            "Phase 4 (productivity)\n"
            "- add task <text>\n"
            "- list tasks\n"
            "- done task <id>\n"
            "- remember <key> = <value>\n"
            "- recall <key>\n"
            "- list memory\n"
            "\n"
            "AI routing\n"
            "- ai <query>\n"
            "- auth status\n"
            "\n"
            "System\n"
            "- status\n"
            "- system shutdown\n"
            "- system restart\n"
            "- doctor\n"
            "- help\n"
            "- exit"
        )

    def process(self, command: str) -> str:
        cmd = self._normalize_command(command)
        low = cmd.lower()

        if not cmd:
            response = "Empty command"
            self._audit_command(cmd, response, route="empty")
            return response

        if low in {"system shutdown", "system poweroff", "shutdown now"}:
            response = self.system_shutdown()
            self._audit_command(cmd, response, route="system-shutdown")
            return response

        if low in {"system restart", "system reboot", "restart now"}:
            response = self.system_restart()
            self._audit_command(cmd, response, route="system-restart")
            return response

        if any(pattern in low for pattern in self.blocked_patterns):
            response = "Command blocked for safety"
            self._audit_command(cmd, response, route="safety")
            return response

        route = "unknown"

        if low in {"help", "commands"}:
            route = "help"
            response = self.help_text()
        elif low.startswith("ai "):
            route = "ai-router"
            response = self._execute_with_action_executor(cmd[3:].strip())
        elif low in {"auth status", "authentication status"}:
            route = "auth-status"
            response = self._auth_status()
        elif low == "status":
            route = "status"
            response = self.system_status()
        elif low == "doctor":
            route = "doctor"
            response = self.doctor_check()
        elif low in {"hi", "hello", "hey"}:
            route = "chat"
            response = self.general_chat(cmd)
        elif low in {"play that", "play it", "play this", "play that on youtube", "play it on youtube"}:
            route = "youtube-play-last"
            response = self.youtube_play(self.last_media_query) if self.last_media_query else "No previous media to play. Try: youtube search <query>"
        elif low in {"play that song on spotify", "play this song on spotify", "play that on spotify", "play on spotify"}:
            route = "spotify-play-last"
            response = self.play_spotify(self.last_media_query)
        else:
            youtube_query = self._extract_youtube_query(cmd)
            if youtube_query:
                route = "youtube-play" if (low.startswith("play ") or " play " in f" {low} ") else "youtube-search"
                response = self.youtube_play(youtube_query) if route == "youtube-play" else self.youtube_search(youtube_query)
            else:
                natural = self._process_natural(cmd)
                if natural is not None:
                    route = "natural"
                    response = natural
                elif low == "open browser":
                    route = "open-browser"
                    response = self.open_chrome()
                elif low.startswith("open website "):
                    route = "open-website"
                    response = self.open_website(cmd[len("open website "):].strip())
                elif low.startswith("open youtube search "):
                    route = "youtube-search"
                    response = self.youtube_search(cmd[len("open youtube search "):].strip())
                elif low.startswith("open youtube and search "):
                    route = "youtube-search"
                    response = self.youtube_search(cmd[len("open youtube and search "):].strip())
                elif low.startswith("open youtube for "):
                    route = "youtube-search"
                    response = self.youtube_search(cmd[len("open youtube for "):].strip())
                elif low.startswith("open "):
                    route = "open"
                    response = self.quick_open(cmd[len("open "):].strip())
                elif low.startswith("youtube search "):
                    route = "youtube-search"
                    response = self.youtube_search(cmd[len("youtube search "):].strip())
                elif low.startswith("search videos "):
                    route = "youtube-search"
                    response = self.youtube_search(cmd[len("search videos "):].strip())
                elif low.startswith("play music "):
                    route = "youtube-play"
                    response = self.youtube_play(cmd[len("play music "):].strip() + " official audio")
                elif low.startswith("search ") and (low.endswith(" on spotify") or low.endswith(" in spotify")):
                    route = "spotify-search"
                    suffix_len = 11
                    query = cmd[7:-suffix_len].strip()
                    response = self.search_spotify(query)
                elif low.startswith("search ") and low.endswith(" spotify"):
                    route = "spotify-search"
                    query = cmd[7:-8].strip()
                    response = self.search_spotify(query)
                elif low.startswith("play ") and (low.endswith(" on spotify") or low.endswith(" in spotify")):
                    route = "spotify-play"
                    suffix_len = 11
                    query = cmd[5:-suffix_len].strip()
                    response = self.play_spotify(query)
                elif low.startswith("play ") and low.endswith(" spotify"):
                    route = "spotify-play"
                    query = cmd[5:-8].strip()
                    response = self.play_spotify(query)
                elif low.startswith("download file "):
                    route = "download-file"
                    response = self.download_file(cmd[len("download file "):].strip())
                elif low.startswith("download video "):
                    route = "download-video"
                    response = self.download_video(cmd[len("download video "):].strip())
                elif low in {"wifi on", "wifi off"}:
                    route = "wifi"
                    response = self.toggle_wifi(on=low.endswith("on"))
                elif low in {"bluetooth on", "bluetooth off"}:
                    route = "bluetooth"
                    response = self.toggle_bluetooth(on=low.endswith("on"))
                elif low.startswith("add contact "):
                    route = "contact-add"
                    response = self.add_contact_command(cmd[len("add contact "):].strip())
                elif low == "list contacts":
                    route = "contact-list"
                    response = self.list_contacts()
                elif low.startswith("send message "):
                    route = "message"
                    response = self.send_message_shortcut(cmd[len("send message "):].strip())
                elif low == "send message":
                    route = "message"
                    response = "Usage: send message <platform> <person> [message]"
                elif low.startswith("send whatsapp "):
                    route = "whatsapp"
                    response = self.send_whatsapp_message(cmd[len("send whatsapp "):].strip())
                elif low.startswith("send facebook "):
                    route = "facebook"
                    response = self.send_facebook_message(cmd[len("send facebook "):].strip())
                elif low.startswith("send email "):
                    route = "email"
                    response = self.send_email_message(cmd[len("send email "):].strip())
                elif low in {"check email", "check my email", "check inbox", "check my inbox"}:
                    route = "email-check"
                    response = self.check_email_inbox()
                elif low.startswith("audio call "):
                    route = "call-audio"
                    response = self.call_shortcut(cmd[len("audio call "):].strip(), video=False)
                elif low.startswith("video call "):
                    route = "call-video"
                    response = self.call_shortcut(cmd[len("video call "):].strip(), video=True)
                elif low.startswith("research papers "):
                    route = "research-papers"
                    response = self.research_topic(cmd[len("research papers "):].strip(), papers_only=True)
                elif low.startswith("research "):
                    route = "research"
                    response = self.research_topic(cmd[len("research "):].strip(), papers_only=False)
                elif low.startswith("add task "):
                    route = "task-add"
                    response = self.add_task(cmd[len("add task "):].strip())
                elif low == "list tasks":
                    route = "task-list"
                    response = self.list_tasks()
                elif low.startswith("done task "):
                    route = "task-done"
                    response = self.complete_task(cmd[len("done task "):].strip())
                elif low.startswith("remember "):
                    route = "memory-save"
                    response = self.remember_value(cmd[len("remember "):].strip())
                elif low.startswith("recall "):
                    route = "memory-recall"
                    response = self.recall_value(cmd[len("recall "):].strip())
                elif low == "list memory":
                    route = "memory-list"
                    response = self.list_memory()
                else:
                    ai_routed = self._execute_with_action_executor(cmd, suppress_unhandled=True)
                    if ai_routed:
                        route = "ai-router"
                        response = ai_routed
                    else:
                        route = "chat"
                        response = self.general_chat(cmd) or "Unknown command. Type 'help'"

        self._audit_command(cmd, response, route=route)
        return response

    def general_chat(self, message: str):
        text = self._normalize_command(message)
        low = text.lower()

        if not low:
            return None

        quick_replies = {
            "how are you": "I am doing well. I am ready to help you.",
            "how are you?": "I am doing well. I am ready to help you.",
            "what can you do": "I can chat, control apps/web, play/search YouTube, messaging shortcuts, research, tasks, and memory.",
            "what can you do?": "I can chat, control apps/web, play/search YouTube, messaging shortcuts, research, tasks, and memory.",
            "who are you": "I am Jarvis, your assistant for chat and laptop tasks.",
            "who are you?": "I am Jarvis, your assistant for chat and laptop tasks.",
            "hello": "Hello. I am here with you.",
            "hi": "Hi. How can I help you right now?",
            "hey": "Hey. Tell me what you need.",
            "good morning": "Good morning. Hope your day goes great.",
            "good night": "Good night. Rest well.",
            "thank you": "You are welcome.",
            "thanks": "You are welcome.",
        }
        if low in quick_replies:
            reply = quick_replies[low]
            self._remember_chat(text, reply)
            return reply

        if any(phrase in low for phrase in ["i am sad", "i'm sad", "feeling low", "depressed"]):
            reply = "I am with you. Want to talk about what happened?"
            self._remember_chat(text, reply)
            return reply

        if any(phrase in low for phrase in ["i am happy", "i'm happy", "feeling good", "great day"]):
            reply = "That is great to hear. Keep the momentum going."
            self._remember_chat(text, reply)
            return reply

        if any(low.startswith(prefix) for prefix in ["how ", "what ", "why ", "who ", "when ", "where ", "can you ", "could you ", "tell me ", "explain "]):
            pass

        if not self._chatbot_checked:
            self._chatbot_fn = self._lazy_import("_chatbot_checked", "_chatbot_fn", "core.chatbot", "SmartChatBot")

        if self._chatbot_fn:
            try:
                with redirect_stdout(io.StringIO()):
                    response = self._chatbot_fn(text)
                if isinstance(response, str) and response.strip():
                    cleaned = response.strip()
                    if "having trouble connecting" in cleaned.lower():
                        fallback = "I can still chat and help with tasks. Add API keys in .env for stronger internet-backed answers."
                        self._remember_chat(text, fallback)
                        return fallback
                    self._remember_chat(text, cleaned)
                    return cleaned
            except Exception:
                self.logger.debug("Chatbot call failed", exc_info=True)

        reply = f"I heard you: {text}. I can chat normally and also run laptop commands."
        self._remember_chat(text, reply)
        return reply

    def _get_action_executor(self):
        executor_cls = self._lazy_import("_executor_checked", "_executor", "core.action_executor", "ActionExecutor")
        if executor_cls is None:
            return None
        if isinstance(executor_cls, type):
            try:
                self._executor = executor_cls()
            except Exception as exc:
                self.logger.debug("ActionExecutor init failed: %s", exc)
                self._executor = None
        return self._executor

    def _execute_with_action_executor(self, query: str, suppress_unhandled: bool = False):
        text = (query or "").strip()
        if not text:
            return None if suppress_unhandled else "Missing AI query"

        executor = self._get_action_executor()
        if not executor:
            return None if suppress_unhandled else "AI router is unavailable"

        try:
            result = executor.execute_query(text)
            if not isinstance(result, str):
                return None if suppress_unhandled else "AI router returned invalid result"
            response = result.strip()
            return response or (None if suppress_unhandled else "AI route executed")
        except JarvisError as exc:
            self.logger.debug("AI routing handled exception: %s", exc)
            return None if suppress_unhandled else str(exc)
        except Exception:
            self.logger.debug("AI routing failed", exc_info=True)
            return None if suppress_unhandled else "AI routing failed"

    def _get_auth_class(self):
        return self._lazy_import("_auth_checked", "_auth_cls", "core.auth", "EnhancedAdminOnlyAuth")

    def _auth_status(self):
        auth_cls = self._get_auth_class()
        if not auth_cls:
            return "Authentication module unavailable"

        try:
            auth = auth_cls()
            status = "configured" if auth.setup_completed else "not configured"
            return f"Authentication status: {status}"
        except Exception as exc:
            return f"Authentication status check failed: {exc}"

    def _remember_chat(self, user_text: str, assistant_text: str):
        try:
            self.chat_history.append(
                {
                    "time": datetime.now().isoformat(timespec="seconds"),
                    "user": user_text,
                    "assistant": assistant_text,
                }
            )
            self.chat_history = self.chat_history[-self.max_chat_history :]
            self._save_json(self.chat_history_file, self.chat_history)
        except Exception as exc:
            self.logger.debug("Failed to persist chat history: %s", exc)

    def _audit_command(self, command: str, response: str, route: str = "unknown"):
        try:
            entry = {
                "time": datetime.now().isoformat(timespec="seconds"),
                "route": route,
                "command": command,
                "response": (response or "")[:300],
            }
            with open(self.audit_log_file, "a", encoding="utf-8") as file:
                file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as exc:
            self.logger.debug("Failed to write audit log: %s", exc)

    def _load_env_like(self):
        values = {}
        env_path = Path(".env")
        if not env_path.exists():
            return values
        try:
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
        except Exception:
            return {}
        return values

    def doctor_check(self) -> str:
        env_values = self._load_env_like()

        def has_env(key: str):
            return bool(os.getenv(key) or env_values.get(key))

        checks = []
        checks.append(("GROQ_API_KEY", has_env("GroqAPIKey") or has_env("GROQ_API_KEY")))
        checks.append(("xAI_API_KEY", has_env("xAI_API_KEY") or has_env("XAI_API_KEY")))
        checks.append(("DEEPSEEK_API_KEY", has_env("DeepSeek_API_KEY") or has_env("DEEPSEEK_API_KEY")))
        checks.append(("COHERE_API_KEY", has_env("CohereAPIKeys") or has_env("COHERE_API_KEY")))
        checks.append(("TAVILY_API_KEY", has_env("Tavily_API_KEY") or has_env("TAVILY_API_KEY")))
        checks.append(("QDRANT_API_KEY", has_env("Quadrant_API_KEY") or has_env("QDRANT_API_KEY")))
        checks.append(("DEEPGRAM_API_KEY", has_env("Deepgram_API_KEY") or has_env("DEEPGRAM_API_KEY")))
        checks.append(("HUGGINGFACE_API_KEY", has_env("HUGGINGFACE_API_KEY") or has_env("HF_API_KEY") or has_env("HUGGINGFACEAPIKEY")))

        tools = []
        for tool in ["nmcli", "rfkill", "yt-dlp", "xdg-open"]:
            tools.append((tool, bool(shutil.which(tool))))

        files = []
        for path in [self.contacts_file, self.tasks_file, self.memory_file, self.chat_history_file, self.audit_log_file]:
            files.append((str(path), path.exists()))

        lines = ["Doctor report", f"Parser: {self.PARSER_VERSION}", "", "API keys"]
        for name, ok in checks:
            lines.append(f"- {name}: {'OK' if ok else 'MISSING'}")

        lines.append("")
        lines.append("System tools")
        for name, ok in tools:
            lines.append(f"- {name}: {'OK' if ok else 'MISSING'}")

        lines.append("")
        lines.append("Data files")
        for name, ok in files:
            lines.append(f"- {name}: {'OK' if ok else 'NOT_FOUND'}")

        lines.append("")
        lines.append("Messaging readiness")
        lines.append(f"- Saved contacts: {len(self.contacts)}")
        lines.append("- Tip: for WhatsApp, save phone with: add contact <name> on whatsapp <phone>")
        lines.append(f"- Chat memory turns: {len(self.chat_history)}")
        return "\n".join(lines)

    def _normalize_command(self, command: str) -> str:
        text = unicodedata.normalize("NFKC", command or "")
        text = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
        text = text.replace("\ufeff", "")
        text = " ".join(text.split())
        return text.strip()

    def _extract_youtube_query(self, command: str):
        text = command.strip()
        low = text.lower()

        if low in {"open youtube", "youtube"}:
            webbrowser.open("https://www.youtube.com")
            return None

        patterns = [
            r"^open\s+youtube\s+search\s+(.+)$",
            r"^open\s+youtube\s+seach\s+(.+)$",
            r"^open\s+youtube\s+serach\s+(.+)$",
            r"^open\s+youtube\s+and\s+search\s+(.+)$",
            r"^open\s+youtube\s+for\s+(.+)$",
            r"^youtube\s+search\s+(.+)$",
            r"^youtube\s+seach\s+(.+)$",
            r"^youtube\s+serach\s+(.+)$",
            r"^search\s+(.+?)\s+on\s+youtube$",
            r"^seach\s+(.+?)\s+on\s+youtube$",
            r"^search\s+youtube\s+for\s+(.+)$",
            r"^find\s+(.+?)\s+on\s+youtube$",
            r"^play\s+(.+?)\s+(?:on|in)\s+youtube$",
        ]

        for pattern in patterns:
            match = re.match(pattern, low)
            if match:
                return match.group(1).strip()

        if low.startswith("play ") and "youtube" in low:
            cleaned = re.sub(r"\b(play|on|in|the|for|and|youtube|search)\b", " ", low)
            query = " ".join(cleaned.split())
            if query:
                return query

        if "youtube" in low and "search" in low:
            cleaned = re.sub(r"\b(open|on|in|the|for|and|youtube|search)\b", " ", low)
            query = " ".join(cleaned.split())
            if query:
                return query

        return None

    def quick_open(self, target: str) -> str:
        item = target.strip().lower()
        if not item:
            return "Usage: open <target>"

        if item.startswith("youtube"):
            rest = item[len("youtube"):].strip(" :-")
            if not rest:
                webbrowser.open("https://www.youtube.com")
                return "Opened youtube"
            rest = re.sub(r"^(search|seach|serach)\s+", "", rest)
            rest = re.sub(r"^and\s+(search|seach|serach)\s+", "", rest)
            if rest:
                return self.youtube_search(rest)
            webbrowser.open("https://www.youtube.com")
            return "Opened youtube"

        quick_sites = {
            "facebook": "https://www.facebook.com",
            "messenger": "https://www.messenger.com",
            "instagram": "https://www.instagram.com",
            "whatsapp": "https://web.whatsapp.com",
            "youtube": "https://www.youtube.com",
            "gmail": "https://mail.google.com",
            "drive": "https://drive.google.com",
            "google": "https://www.google.com",
            "linkedin": "https://www.linkedin.com",
            "email": "https://mail.google.com",
        }

        if item in {"bluetooth", "bluetooth on"}:
            return self.toggle_bluetooth(on=True)
        if item == "bluetooth off":
            return self.toggle_bluetooth(on=False)

        if item in {"wifi", "wifi on"}:
            return self.toggle_wifi(on=True)
        if item == "wifi off":
            return self.toggle_wifi(on=False)

        if item in {"settings", "setting", "system settings"}:
            return self.open_system_settings()

        if item in {"files", "file manager", "folders", "folder"}:
            return self.open_files_manager()

        if item in {"downloads", "download"}:
            return self.open_named_folder("Downloads")

        if item in {"documents", "document"}:
            return self.open_named_folder("Documents")

        if item in {"pictures", "picture", "photos", "photo"}:
            return self.open_named_folder("Pictures")

        if item in {"videos", "video"}:
            return self.open_named_folder("Videos")

        if item in {"music", "songs", "song"}:
            return self.open_named_folder("Music")

        if item in {"photoshop", "gimp"}:
            return self.open_gimp()

        if item in {"illustrator", "terminal", "linux terminal", "shell"}:
            return self.open_terminal_app()

        if item in {"vlc", "premiere"}:
            return self.open_vlc()

        if item == "spotify":
            return self.open_spotify()

        if item in {"steam", "epic", "epic games", "epicgames"}:
            return self.open_game_launcher(item)

        if item in {"google", "chrome"}:
            return self.open_chrome()

        if item == "firefox":
            return self.open_firefox()

        if item in {"audio", "music", "audio files", "music files"}:
            return self.open_audio_files()

        if item in quick_sites:
            webbrowser.open(quick_sites[item])
            return f"Opened {item}"

        return self.open_website(target)

    def _process_natural(self, command: str):
        text = command.strip()
        low = text.lower()

        wifi_pattern = re.match(r"^turn\s+(on|off)\s+wifi$", low)
        if wifi_pattern:
            return self.toggle_wifi(on=wifi_pattern.group(1) == "on")

        bluetooth_pattern = re.match(r"^turn\s+(on|off)\s+bluetooth$", low)
        if bluetooth_pattern:
            return self.toggle_bluetooth(on=bluetooth_pattern.group(1) == "on")

        youtube_pattern = re.match(r"^search\s+(.+?)\s+on\s+youtube$", low)
        if youtube_pattern:
            return self.youtube_search(youtube_pattern.group(1).strip())

        youtube_pattern_2 = re.match(r"^search\s+youtube\s+for\s+(.+)$", low)
        if youtube_pattern_2:
            return self.youtube_search(youtube_pattern_2.group(1).strip())

        youtube_pattern_3 = re.match(r"^open\s+youtube\s+search\s+(.+)$", low)
        if youtube_pattern_3:
            return self.youtube_search(youtube_pattern_3.group(1).strip())

        message_pattern = re.match(
            rf"^send message to\s+(.+?)\s+on\s+({self._platform_pattern})(?:\s+saying\s+(.+))?$",
            low,
        )
        if message_pattern:
            person = message_pattern.group(1).strip()
            platform = message_pattern.group(2).strip()
            message = message_pattern.group(3).strip() if message_pattern.group(3) else ""
            return self.send_message_to_platform(platform, person, message)

        message_pattern_2 = re.match(r"^send message to\s+(.+?)\s+saying\s+(.+)$", low)
        if message_pattern_2:
            person = message_pattern_2.group(1).strip()
            message = message_pattern_2.group(2).strip()
            return self.send_message_to_platform("whatsapp", person, message)

        message_pattern_3 = re.match(rf"^send\s+(.+?)\s+to\s+(.+?)\s+on\s+({self._platform_pattern})$", low)
        if message_pattern_3:
            message = message_pattern_3.group(1).strip()
            person = message_pattern_3.group(2).strip()
            platform = message_pattern_3.group(3).strip()
            return self.send_message_to_platform(platform, person, message)

        message_pattern_4 = re.match(rf"^message\s+(.+?)\s+on\s+({self._platform_pattern})(?:\s+(.+))?$", low)
        if message_pattern_4:
            person = message_pattern_4.group(1).strip()
            platform = message_pattern_4.group(2).strip()
            message = message_pattern_4.group(3).strip() if message_pattern_4.group(3) else ""
            return self.send_message_to_platform(platform, person, message)

        message_pattern_5 = re.match(rf"^send message on\s+({self._platform_pattern})\s+to\s+(.+?)(?:\s+saying\s+(.+))?$", low)
        if message_pattern_5:
            platform = message_pattern_5.group(1).strip()
            person = message_pattern_5.group(2).strip()
            message = message_pattern_5.group(3).strip() if message_pattern_5.group(3) else ""
            return self.send_message_to_platform(platform, person, message)

        message_pattern_6 = re.match(r"^send message to\s+(.+?)(?:\s+(.+))?$", low)
        if message_pattern_6:
            person = message_pattern_6.group(1).strip()
            message = message_pattern_6.group(2).strip() if message_pattern_6.group(2) else ""
            return self.send_message_to_platform("whatsapp", person, message)

        audio_pattern = re.match(
            rf"^audio call\s+(.+?)\s+on\s+({self._platform_pattern})$",
            low,
        )
        if audio_pattern:
            person = audio_pattern.group(1).strip()
            platform = audio_pattern.group(2).strip()
            return self.open_call(platform, person, video=False)

        video_pattern = re.match(
            rf"^video call\s+(.+?)\s+on\s+({self._platform_pattern})$",
            low,
        )
        if video_pattern:
            person = video_pattern.group(1).strip()
            platform = video_pattern.group(2).strip()
            return self.open_call(platform, person, video=True)

        return None

    def open_system_settings(self) -> str:
        candidates = [
            ["gnome-control-center"],
            ["systemsettings5"],
            ["kcmshell5", "kcm_lookandfeel"],
            ["xfce4-settings-manager"],
            ["mate-control-center"],
        ]
        if self._run_first_available(candidates):
            return "Opened system settings"
        return "Could not open settings app on this desktop environment"

    def open_files_manager(self) -> str:
        if self._open_path(Path.home()):
            return "Opened files"
        return "Could not open file manager"

    def open_named_folder(self, folder_name: str) -> str:
        target = Path.home() / folder_name
        target.mkdir(parents=True, exist_ok=True)
        if self._open_path(target):
            return f"Opened {folder_name}"
        return f"Could not open {folder_name}"

    def _open_path(self, path: Path) -> bool:
        target = str(path)
        candidates = [
            ["xdg-open", target],
            ["nautilus", target],
            ["dolphin", target],
            ["thunar", target],
            ["pcmanfm", target],
        ]
        return self._run_first_available(candidates)

    def open_gimp(self) -> str:
        candidates = [
            ["gimp"],
            ["flatpak", "run", "org.gimp.GIMP"],
            ["snap", "run", "gimp"],
        ]
        if self._run_first_available(candidates):
            return "Opened GIMP"
        return "Could not open GIMP"

    def open_terminal_app(self) -> str:
        candidates = [
            ["x-terminal-emulator"],
            ["gnome-terminal"],
            ["konsole"],
            ["xfce4-terminal"],
            ["tilix"],
            ["kitty"],
            ["alacritty"],
        ]
        if self._run_first_available(candidates):
            return "Opened terminal"
        return "Could not open terminal"

    def open_spotify(self) -> str:
        candidates = [
            ["spotify"],
            ["flatpak", "run", "com.spotify.Client"],
            ["snap", "run", "spotify"],
        ]
        if self._run_first_available(candidates):
            return "Opened Spotify"
        return "Could not open Spotify"

    def play_spotify(self, query: str = None) -> str:
        if not query:
            launch = self.open_spotify()
            if launch.startswith("Opened"):
                return "Opened Spotify"
            return launch

        launch = self.open_spotify()
        track = self._spotify_first_track(query)
        if track:
            track_id = track.get("id")
            track_name = track.get("name", query)
            artist = track.get("artist", "")
            uri = f"spotify:track:{track_id}"
            track_url = f"https://open.spotify.com/track/{track_id}"
            opened = False
            try:
                if shutil.which("xdg-open"):
                    subprocess.Popen(["xdg-open", uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    opened = True
            except Exception:
                opened = False

            if not opened:
                try:
                    webbrowser.open(track_url)
                    opened = True
                except Exception:
                    opened = False

            if opened:
                self._spotify_try_play_now()
                by_artist = f" by {artist}" if artist else ""
                return f"Playing on Spotify: {track_name}{by_artist}"

        search_uri = f"spotify:search:{quote_plus(query)}"
        opened_uri = False
        try:
            if shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", search_uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                opened_uri = True
        except Exception:
            opened_uri = False

        self._spotify_try_play_now()

        if opened_uri:
            return f"Opened Spotify and tried to play: {query}"

        return self.search_spotify(query)

    def search_spotify(self, query: str) -> str:
        if not query:
            return "Missing Spotify search query"
        launch = self.open_spotify()
        search_url = f"https://open.spotify.com/search/{quote_plus(query)}"
        try:
            webbrowser.open(search_url)
            if launch.startswith("Opened"):
                return f"Opened Spotify search for: {query}"
            return f"Opened Spotify web search for: {query}"
        except Exception:
            return launch if launch else "Could not open Spotify"

    def _spotify_first_track(self, query: str):
        # Avoid undocumented Spotify web-player token endpoints.
        # Fallback behavior is to open Spotify search URI/web search instead.
        _ = query
        return None

    def _spotify_try_play_now(self):
        if not shutil.which("playerctl"):
            return
        try:
            subprocess.run(["playerctl", "-p", "spotify", "play"], capture_output=True, text=True, timeout=4)
        except Exception:
            pass

    def open_vlc(self) -> str:
        candidates = [
            ["vlc"],
            ["flatpak", "run", "org.videolan.VLC"],
            ["snap", "run", "vlc"],
        ]
        if self._run_first_available(candidates):
            return "Opened VLC"
        return "Could not open VLC"

    def open_chrome(self) -> str:
        candidates = [
            ["google-chrome", "https://www.google.com"],
            ["google-chrome-stable", "https://www.google.com"],
            ["chromium", "https://www.google.com"],
            ["chromium-browser", "https://www.google.com"],
        ]
        if self._run_first_available(candidates):
            return "Opened Chrome"

        webbrowser.open("https://www.google.com")
        return "Opened Google in default browser"

    def open_firefox(self) -> str:
        candidates = [
            ["firefox", "https://www.google.com"],
            ["firefox-esr", "https://www.google.com"],
        ]
        if self._run_first_available(candidates):
            return "Opened Firefox"
        return "Could not open Firefox"

    def open_audio_files(self) -> str:
        exts = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wma"}
        collection_dir = CACHE_DIR / "audio_collection"
        collection_dir.mkdir(parents=True, exist_ok=True)
        if not validate_path_in_base(collection_dir, CACHE_DIR):
            return "Audio collection path is invalid"

        for item in collection_dir.iterdir():
            try:
                if item.is_file() or item.is_symlink():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except Exception:
                continue

        roots = [
            Path.home() / "Music",
            Path.home() / "Downloads",
            Path.home() / "Documents",
            Path.home() / "Desktop",
            Path.home() / "Videos",
        ]
        skip = {
            ".cache", ".config", ".local", ".venv", "node_modules", "__pycache__", "site-packages",
            "lib", "libs", "env", "venv", "anaconda3", "miniconda3",
        }

        audio_files = []
        folder_counts = {}
        for root in roots:
            if not root.exists():
                continue
            for base, dirs, files in os.walk(root):
                dirs[:] = [
                    name for name in dirs
                    if name not in skip and not name.startswith(".") and not name.lower().endswith("_env")
                ]
                for file_name in files:
                    extension = Path(file_name).suffix.lower()
                    if extension in exts:
                        file_path = Path(base) / file_name
                        audio_files.append(file_path)
                        folder_counts[str(file_path.parent)] = folder_counts.get(str(file_path.parent), 0) + 1
                if len(audio_files) >= 2000:
                    break
            if len(audio_files) >= 2000:
                break

        if not audio_files:
            if self._open_path(collection_dir):
                return f"No audio files found. Opened {collection_dir}"
            return "No audio files found"

        gathered = 0
        for index, source in enumerate(audio_files[:600], start=1):
            safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", source.name)
            target = collection_dir / f"{index:03d}_{safe_name}"
            try:
                target.symlink_to(source.resolve())
                gathered += 1
            except Exception:
                continue

        if gathered > 0 and self._open_path(collection_dir):
            return f"Gathered {gathered} audio files in {collection_dir}"

        preferred_root = (Path.home() / "Music").resolve()
        music_folders = [(folder, count) for folder, count in folder_counts.items() if str(folder).startswith(str(preferred_root))]
        if music_folders:
            primary_folder = Path(sorted(music_folders, key=lambda item: item[1], reverse=True)[0][0])
        else:
            primary_folder = Path(sorted(folder_counts.items(), key=lambda item: item[1], reverse=True)[0][0])

        if self._open_path(primary_folder):
            return f"Found {len(audio_files)} audio files. Opened {primary_folder}"
        return f"Found {len(audio_files)} audio files"

    def open_game_launcher(self, target: str) -> str:
        item = (target or "").strip().lower()
        if item in {"epic", "epic games", "epicgames"}:
            epic_candidates = [
                ["heroic"],
                ["legendary"],
                ["lutris"],
            ]
            if self._run_first_available(epic_candidates):
                return "Opened Epic Games launcher"
            return "Could not open Epic Games launcher"

        steam_candidates = [
            ["steam"],
            ["flatpak", "run", "com.valvesoftware.Steam"],
        ]
        if self._run_first_available(steam_candidates):
            return "Opened Steam"
        return "Could not open Steam"

    def system_shutdown(self) -> str:
        return "App shutdown requested"

    def system_restart(self) -> str:
        return "App restart requested"

    def _run_first_available(self, commands) -> bool:
        for cmd in commands:
            executable = cmd[0]
            if shutil.which(executable):
                try:
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
                except Exception:
                    continue
        return False

    def open_website(self, target: str) -> str:
        if not target:
            return "Missing website"

        normalized = target.strip()
        if not normalized.startswith(("http://", "https://")):
            if "." in normalized:
                normalized = f"https://{normalized}"
            else:
                normalized = f"https://www.google.com/search?q={quote_plus(target)}"

        if not validate_url(normalized):
            return "Blocked: invalid or unsupported URL"

        webbrowser.open(normalized)
        return f"Opened {normalized}"

    def youtube_search(self, query: str) -> str:
        if not query:
            return "Missing search query"
        self.last_media_query = query.strip()
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        webbrowser.open(url)
        return f"Opened YouTube search for: {query}"

    def youtube_play(self, query: str) -> str:
        if not query:
            return "Missing play query"

        normalized = query.strip()
        self.last_media_query = normalized

        ytdlp = shutil.which("yt-dlp")
        if ytdlp:
            try:
                result = subprocess.run(
                    [ytdlp, "--no-warnings", "--skip-download", "--get-id", f"ytsearch1:{normalized}"],
                    capture_output=True,
                    text=True,
                    timeout=40,
                )
                if result.returncode == 0:
                    video_id = (result.stdout or "").strip().splitlines()[0].strip()
                    if video_id:
                        url = f"https://www.youtube.com/watch?v={video_id}"
                        webbrowser.open(url)
                        return f"Playing on YouTube: {normalized}"
            except Exception:
                pass

        try:
            search_url = f"https://www.youtube.com/results?search_query={quote_plus(normalized)}"
            response = requests.get(
                search_url,
                timeout=20,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if response.status_code == 200:
                matches = re.findall(r"watch\?v=([a-zA-Z0-9_-]{11})", response.text)
                if matches:
                    first_video = matches[0]
                    webbrowser.open(f"https://www.youtube.com/watch?v={first_video}")
                    return f"Playing on YouTube: {normalized}"
        except Exception:
            pass

        return self.youtube_search(normalized)

    def add_contact_command(self, payload: str) -> str:
        return self.contact_service.add_contact_command(payload)

    def list_contacts(self) -> str:
        return self.contact_service.list_contacts()

    def send_message_shortcut(self, payload: str) -> str:
        return self.contact_service.send_message_shortcut(payload, self.send_message_to_platform)

    def send_message_to_platform(self, platform: str, person: str, message: str = "") -> str:
        return self.messaging_service.send_message_web(platform, person, message)

    def _get_username(self) -> str:
        return ConfigManager.get("Username", "USERNAME", default="user")

    def send_whatsapp_message(self, payload: str) -> str:
        """Send WhatsApp message using WhatsApp Business API."""
        match = re.match(r"^to\s+(\+\d+)\s+saying\s+(.+)$", payload, re.IGNORECASE)
        if not match:
            return "Usage: send whatsapp to +1234567890 saying Your message"

        phone = match.group(1).strip()
        message = match.group(2).strip()

        from .chatbot import CommunicationManager
        from .channels.whatsapp import WhatsAppChannel

        config = CommunicationManager.get_channel_config("whatsapp")
        ok, msg = self._require_config(
            config,
            ["api_key", "phone_number_id"],
            channel_name="WhatsApp",
            enable_key_hint="WHATSAPP_ENABLED",
        )
        if not ok:
            return msg

        channel = WhatsAppChannel(config)
        success = channel.send(message, phone)

        if success:
            CommunicationManager.log_message(
                self._get_username(),
                phone,
                "whatsapp",
                "text_message",
                message,
                "sent",
            )
            return f"WhatsApp message sent to {phone}"

        CommunicationManager.log_message(
            self._get_username(),
            phone,
            "whatsapp",
            "text_message",
            message,
            "failed",
        )
        return "Failed to send WhatsApp message"

    def send_facebook_message(self, payload: str) -> str:
        """Send Facebook Messenger message using Graph API."""
        match = re.match(r"^to\s+(.+?)\s+saying\s+(.+)$", payload, re.IGNORECASE)
        if not match:
            return "Usage: send facebook to user_id saying Your message"

        recipient = match.group(1).strip()
        message = match.group(2).strip()

        from .chatbot import CommunicationManager
        from .channels.facebook import FacebookMessengerChannel

        config = CommunicationManager.get_channel_config("facebook")
        ok, msg = self._require_config(
            config,
            ["page_access_token"],
            channel_name="Facebook",
            enable_key_hint="FACEBOOK_ENABLED",
        )
        if not ok:
            return msg

        channel = FacebookMessengerChannel(config)
        success = channel.send(message, recipient)

        CommunicationManager.log_message(
            self._get_username(),
            recipient,
            "facebook",
            "text_message",
            message,
            "sent" if success else "failed",
        )

        return f"Facebook message sent to {recipient}" if success else "Failed to send Facebook message"

    def send_email_message(self, payload: str) -> str:
        """Send an email using SMTP credentials from environment config."""
        match = re.match(r"^to\s+(.+?)(?:\s+subject\s+(.+?))?\s+saying\s+(.+)$", payload, re.IGNORECASE)
        if not match:
            return "Usage: send email to recipient@example.com subject Optional subject saying Email body"

        recipient = match.group(1).strip()
        subject = (match.group(2) or "Message from JARVIS").strip()
        body = match.group(3).strip()

        from .chatbot import CommunicationManager
        from .channels.email_channel import EmailChannel

        config = CommunicationManager.get_channel_config("email")
        ok, msg = self._require_config(
            config,
            ["email", "password", "smtp_server"],
            channel_name="Email",
            enable_key_hint="EMAIL_ENABLED",
        )
        if not ok:
            return msg

        channel = EmailChannel(config)
        success = channel.send(body, recipient, subject)

        CommunicationManager.log_message(
            self._get_username(),
            recipient,
            "email",
            "email_message",
            f"Subject: {subject}\n{body}",
            "sent" if success else "failed",
        )

        return f"Email sent to {recipient}" if success else "Failed to send email"

    def check_email_inbox(self) -> str:
        """Manually check inbox once via IMAP and enqueue unseen emails."""
        from .chatbot import CommunicationManager
        from .channels.email_channel import EmailChannel

        config = CommunicationManager.get_channel_config("email")
        ok, msg = self._require_config(
            config,
            ["email", "password", "imap_server"],
            channel_name="Email",
            enable_key_hint="EMAIL_ENABLED",
        )
        if not ok:
            return msg

        channel = EmailChannel(config)
        result = channel.check_inbox_once()
        processed = int(result.get("processed", 0))
        errors = result.get("errors", [])

        if errors:
            return f"Email check finished with errors: {' | '.join(str(e) for e in errors[:2])}"
        return f"Email check complete. New unread messages queued: {processed}"

    def _build_message_action(self, platform: str, person: str, message: str = ""):
        return self.messaging_service.build_web_message_action(platform, person, message)

    def _looks_like_phone(self, value: str) -> bool:
        digits = re.sub(r"\D", "", value or "")
        return 8 <= len(digits) <= 15

    def call_shortcut(self, payload: str, video: bool) -> str:
        match = re.match(rf"^(.+?)\s+on\s+({self._platform_pattern})$", payload, re.IGNORECASE)
        if not match:
            mode = "video" if video else "audio"
            return f"Usage: {mode} call <person> on <platform>"

        person = match.group(1).strip().lower()
        platform = match.group(2).strip().lower()
        return self.open_call(platform, person, video=video)

    def open_call(self, platform: str, person: str, video: bool) -> str:
        return self.messaging_service.open_call(platform, person, video)

    def _resolve_contact_handle(self, person: str, platform: str):
        name = person.strip().lower()
        if name in self.contacts and platform in self.contacts[name]:
            return self.contacts[name][platform]
        return None

    def _safe_filename(self, value: str) -> str:
        value = value.strip().replace("/", "_").replace("\\", "_")
        return re.sub(r"[^a-zA-Z0-9._-]", "_", value) or "download.bin"

    def _download_allowlist(self):
        configured = ConfigManager.get("JARVIS_DOWNLOAD_ALLOWLIST", default="").strip()
        if configured:
            return {item.strip().lower() for item in configured.split(",") if item.strip()}
        return {
            "raw.githubusercontent.com",
            "github.com",
            "files.pythonhosted.org",
            "pypi.org",
            "upload.wikimedia.org",
            "archive.org",
        }

    def _blocked_download_extension(self, filename: str) -> bool:
        suffix = Path(filename).suffix.lower().strip()
        blocked = {".exe", ".dll", ".bat", ".cmd", ".scr", ".ps1", ".vbs", ".js", ".jar"}
        return suffix in blocked

    def _looks_malicious_chunk(self, chunk: bytes) -> bool:
        if not chunk:
            return False
        signatures = [b"MZ", b"\x7fELF"]
        lower = chunk[:4096].lower()
        for sig in signatures:
            if sig.lower() in lower:
                return True
        return False

    def download_file(self, payload: str) -> str:
        match = re.match(r"^(\S+)(?:\s+to\s+(.+))?$", payload)
        if not match:
            return "Usage: download file <url> [to <filename>]"

        url = match.group(1)
        custom_name = match.group(2)

        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return "Only http/https downloads are allowed"
        allowlist = self._download_allowlist()
        if not validate_url(url, allowlist=allowlist):
            return "Download blocked: domain is not in allowlist"

        filename = custom_name.strip() if custom_name else os.path.basename(parsed.path) or "download.bin"
        filename = self._safe_filename(filename)
        if self._blocked_download_extension(filename):
            return "Download blocked: executable/script file types are not allowed"
        target = self.download_dir / filename
        if not validate_path_in_base(target, self.download_dir):
            return "Download blocked: invalid target path"

        max_size_mb = max(1, ConfigManager.get_int("JARVIS_DOWNLOAD_MAX_MB", default=50))
        max_size_bytes = max_size_mb * 1024 * 1024

        try:
            with requests.get(url, stream=True, timeout=30) as response:
                response.raise_for_status()
                content_length = response.headers.get("Content-Length")
                if content_length:
                    try:
                        if int(content_length) > max_size_bytes:
                            return f"Download blocked: file exceeds {max_size_mb} MB limit"
                    except Exception:
                        pass

                written = 0
                first_chunk = True
                blocked_reason = ""
                with open(target, "wb") as file:
                    for chunk in response.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            if first_chunk and self._looks_malicious_chunk(chunk):
                                blocked_reason = "Download blocked: suspicious file signature"
                                break
                            first_chunk = False
                            written += len(chunk)
                            if written > max_size_bytes:
                                blocked_reason = f"Download blocked: file exceeds {max_size_mb} MB limit"
                                break
                            file.write(chunk)
                if blocked_reason:
                    try:
                        target.unlink(missing_ok=True)
                    except Exception:
                        pass
                    return blocked_reason
            return f"Downloaded file to {target}"
        except Exception as exc:
            return f"Download failed: {exc}"

    def download_video(self, payload: str) -> str:
        if not payload:
            return "Usage: download video <url or query>"

        ytdlp = shutil.which("yt-dlp")
        if not ytdlp:
            self.youtube_search(payload)
            return "yt-dlp is not installed. Opened YouTube search instead"

        target_template = str(self.download_dir / "%(title)s.%(ext)s")
        cmd = [ytdlp, "-o", target_template]

        if payload.startswith(("http://", "https://")):
            cmd.append(payload)
        else:
            cmd.append(f"ytsearch1:{payload}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode == 0:
                return "Video download completed"
            return f"Video download failed: {result.stderr.strip()[:180]}"
        except Exception as exc:
            return f"Video download error: {exc}"

    def toggle_wifi(self, on: bool) -> str:
        state = "on" if on else "off"
        commands = []
        if shutil.which("nmcli"):
            commands.append(["nmcli", "radio", "wifi", state])
        if shutil.which("rfkill"):
            commands.append(["rfkill", "unblock" if on else "block", "wifi"])

        if not commands:
            return "No WiFi control tool found (need nmcli or rfkill)"

        errors = []
        for cmd in commands:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
                if result.returncode == 0:
                    current = self.wifi_enabled()
                    if current is None or current == on:
                        return f"WiFi turned {state}"
                    errors.append(f"{' '.join(cmd)} ran but state did not change")
                else:
                    details = (result.stderr or result.stdout or "").strip()
                    errors.append(f"{' '.join(cmd)}: {details or 'failed'}")
            except Exception as exc:
                errors.append(f"{' '.join(cmd)}: {exc}")

        return f"WiFi command failed: {' | '.join(errors[:3])}"

    def toggle_bluetooth(self, on: bool) -> str:
        state = "on" if on else "off"
        commands = []
        if shutil.which("nmcli"):
            commands.append(["nmcli", "radio", "bluetooth", state])
        if shutil.which("rfkill"):
            commands.append(["rfkill", "unblock" if on else "block", "bluetooth"])
        if shutil.which("bluetoothctl"):
            commands.append(["bluetoothctl", "power", state])

        if not commands:
            return "No Bluetooth control tool found (need nmcli, rfkill, or bluetoothctl)"

        errors = []
        for cmd in commands:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
                if result.returncode == 0:
                    current = self.bluetooth_enabled()
                    if current is None or current == on:
                        return f"Bluetooth turned {state}"
                    errors.append(f"{' '.join(cmd)} ran but state did not change")
                else:
                    details = (result.stderr or result.stdout or "").strip()
                    errors.append(f"{' '.join(cmd)}: {details or 'failed'}")
            except Exception as exc:
                errors.append(f"{' '.join(cmd)}: {exc}")

        return f"Bluetooth command failed: {' | '.join(errors[:3])}"

    def wifi_enabled(self):
        if shutil.which("nmcli"):
            try:
                result = subprocess.run(["nmcli", "radio", "wifi"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    text = (result.stdout or "").strip().lower()
                    if "enabled" in text or text == "on":
                        return True
                    if "disabled" in text or text == "off":
                        return False
            except Exception:
                pass

        if shutil.which("rfkill"):
            try:
                result = subprocess.run(["rfkill", "list", "wifi"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    text = (result.stdout or "").lower()
                    if "soft blocked: no" in text:
                        return True
                    if "soft blocked: yes" in text:
                        return False
            except Exception:
                pass

        return None

    def bluetooth_enabled(self):
        if shutil.which("nmcli"):
            try:
                result = subprocess.run(["nmcli", "radio", "bluetooth"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    text = (result.stdout or "").strip().lower()
                    if "enabled" in text or text == "on":
                        return True
                    if "disabled" in text or text == "off":
                        return False
            except Exception:
                pass

        if shutil.which("rfkill"):
            try:
                result = subprocess.run(["rfkill", "list", "bluetooth"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    text = (result.stdout or "").lower()
                    if "soft blocked: no" in text:
                        return True
                    if "soft blocked: yes" in text:
                        return False
            except Exception:
                pass

        if shutil.which("bluetoothctl"):
            try:
                result = subprocess.run(["bluetoothctl", "show"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    text = (result.stdout or "").lower()
                    if "powered: yes" in text:
                        return True
                    if "powered: no" in text:
                        return False
            except Exception:
                pass

        return None

    def research_topic(self, topic: str, papers_only: bool = False) -> str:
        if not topic:
            return "Missing research topic"

        summary_parts = []

        if not papers_only:
            wiki = self._wikipedia_summary(topic)
            if wiki:
                summary_parts.append("General summary")
                summary_parts.append(wiki)

        papers = self._paper_sources(topic)
        if papers:
            summary_parts.append("Papers")
            for paper in papers:
                summary_parts.append(f"- {paper}")

        if not summary_parts:
            return "No research data found"

        note_text = "\n".join(summary_parts)
        file_path = self._save_research_note(topic, note_text)
        return f"Research ready for {topic}\nSaved: {file_path}\n\n{note_text[:1200]}"

    def _wikipedia_summary(self, topic: str):
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote_plus(topic)}"
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                return None
            data = response.json()
            return data.get("extract")
        except Exception:
            return None

    def _paper_sources(self, topic: str):
        papers = []
        papers.extend(self._arxiv_papers(topic))
        papers.extend(self._crossref_papers(topic))
        deduped = []
        seen = set()
        for item in papers:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        return deduped[:6]

    def _arxiv_papers(self, topic: str):
        try:
            url = (
                "http://export.arxiv.org/api/query?search_query=all:"
                f"{quote_plus(topic)}&start=0&max_results=3"
            )
            response = requests.get(url, timeout=20)
            if response.status_code != 200:
                return []
            text = response.text
            titles = re.findall(r"<title>(.*?)</title>", text, flags=re.DOTALL)
            links = re.findall(r"<id>(http://arxiv.org/abs/.*?)</id>", text)
            if not titles:
                return []
            result = []
            for index, title in enumerate(titles[1:4], start=0):
                clean_title = " ".join(title.split())
                link = links[index + 1] if len(links) > index + 1 else "arXiv"
                result.append(f"{clean_title} ({link})")
            return result
        except Exception:
            return []

    def _crossref_papers(self, topic: str):
        try:
            url = f"https://api.crossref.org/works?query={quote_plus(topic)}&rows=3"
            response = requests.get(url, timeout=20)
            if response.status_code != 200:
                return []
            items = response.json().get("message", {}).get("items", [])
            out = []
            for item in items[:3]:
                title = ""
                if item.get("title"):
                    title = item["title"][0]
                doi = item.get("DOI")
                if title and doi:
                    out.append(f"{title} (https://doi.org/{doi})")
                elif title:
                    out.append(title)
            return out
        except Exception:
            return []

    def _save_research_note(self, topic: str, text: str):
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", topic.strip().lower())[:80] or "topic"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.research_dir / f"{slug}_{stamp}.md"
        with open(path, "w", encoding="utf-8") as file:
            file.write(f"# Research Note: {topic}\n\n{text}\n")
        return path

    def add_task(self, task_text: str) -> str:
        return self.task_service.add_task(task_text)

    def list_tasks(self) -> str:
        return self.task_service.list_tasks()

    def complete_task(self, task_id_text: str) -> str:
        return self.task_service.complete_task(task_id_text)

    def remember_value(self, payload: str) -> str:
        return self.memory_service.remember_value(payload)

    def recall_value(self, key: str) -> str:
        return self.memory_service.recall_value(key)

    def list_memory(self) -> str:
        return self.memory_service.list_memory()

    def system_status(self) -> str:
        wifi_text = self._run_status(["nmcli", "radio", "wifi"], "WiFi")
        bt_text = self._run_status(["rfkill", "list", "bluetooth"], "Bluetooth")
        return f"System status\n{wifi_text}\n{bt_text}\nDownloads: {self.download_dir}"

    def _run_status(self, cmd, label: str) -> str:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                text = (result.stdout or "ok").strip().splitlines()[0]
                return f"{label}: {text}"
            return f"{label}: unavailable"
        except Exception:
            return f"{label}: unavailable"
