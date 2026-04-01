# pyright: reportUndefinedVariable=false, reportGeneralTypeIssues=false
from __future__ import annotations

import datetime
import json
import os
import re
import logging
from pathlib import Path
from typing import Dict, Generator, List

import requests

try:
    from groq import Groq
except Exception:
    Groq = None

from .utils import env_get, load_json, save_json
from .config import ConfigManager
from .resilience import (
    CircuitBreaker,
    ServiceAuthError,
    ServiceError,
    ServiceRequestError,
    retry_with_backoff,
    validate_http_status,
)


VERBOSE = ConfigManager.get_bool("JARVIS_VERBOSE_STARTUP", default=False)
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def _env_map() -> Dict[str, str]:
    return ConfigManager.env_map(str(ENV_PATH))


def _get_api_key(*keys: str) -> str:
    return env_get(*keys, env_map=_env_map())


def _username() -> str:
    return env_get("Username", "USERNAME", default="User", env_map=_env_map())


def _assistant_name() -> str:
    return env_get("Assistantname", "AssistantName", "ASSISTANT_NAME", default="Jarvis", env_map=_env_map())
CONTEXT_WINDOW = ConfigManager.get_int("JARVIS_CONTEXT_WINDOW", default=10)
MAX_HISTORY_TURNS = max(20, ConfigManager.get_int("JARVIS_MAX_HISTORY_TURNS", default=100))
MAX_CONTEXT_MESSAGES = max(8, ConfigManager.get_int("JARVIS_MAX_CONTEXT_MESSAGES", default=24))
MAX_LEGACY_SYNC_MESSAGES = max(4, ConfigManager.get_int("JARVIS_MAX_LEGACY_SYNC_MESSAGES", default=6))

_deepseek_breaker = CircuitBreaker("deepseek", failure_threshold=3, cooldown_seconds=25)
_xai_breaker = CircuitBreaker("xai", failure_threshold=3, cooldown_seconds=25)
_groq_breaker = CircuitBreaker("groq", failure_threshold=3, cooldown_seconds=20)
_openai_stream_breaker = CircuitBreaker("openai_stream", failure_threshold=3, cooldown_seconds=20)
_deepseek_stream_breaker = CircuitBreaker("deepseek_stream", failure_threshold=3, cooldown_seconds=25)
_xai_stream_breaker = CircuitBreaker("xai_stream", failure_threshold=3, cooldown_seconds=25)
logger = logging.getLogger(__name__)


class AIProviderManager:
    def __init__(self):
        self.providers = {
            "groq": {"enabled": True},
            "deepseek": {"enabled": True},
            "xai": {"enabled": True},
            "openai": {"enabled": True},
            "cohere": {"enabled": True},
            "local": {"enabled": True},
        }
        self.provider_health: Dict[str, Dict[str, float]] = {}
        self.local_ollama_url = os.getenv("JARVIS_LOCAL_LLM_URL", "http://127.0.0.1:11434/api/generate")
        self.local_ollama_model = os.getenv("JARVIS_LOCAL_LLM_MODEL", "llama3.2:3b")

    def check_health(self, name: str) -> bool:
        if not self._is_enabled(name):
            return False
        if name != "local":
            return True
        try:
            response = requests.get("http://127.0.0.1:11434/api/tags", timeout=1.8)
            return response.status_code == 200
        except Exception:
            return False

    def _is_enabled(self, name: str) -> bool:
        if name == "groq":
            return bool(_get_api_key("GROQ_API_KEY", "GroqAPIKey", "GROQAPIKEY"))
        if name == "deepseek":
            return bool(_get_api_key("DEEPSEEK_API_KEY", "DeepSeek_API_KEY", "DeepSeekAPIKey"))
        if name == "xai":
            return bool(_get_api_key("XAI_API_KEY", "xAI_API_KEY", "X_AI_API_KEY"))
        if name == "openai":
            return bool(_get_api_key("OPENAI_API_KEY", "OPENAIAPIKEY", "OPEN_AI_API_KEY"))
        if name == "cohere":
            return bool(_get_api_key("COHERE_API_KEY", "CohereAPIKeys", "COHEREAPIKEY"))
        return bool((self.providers.get(name) or {}).get("enabled", False))

    def get_best_provider(self, task_type: str = "chat") -> str:
        healthy = []
        for name in self.providers.keys():
            if not self.check_health(name):
                continue
            stats = self.provider_health.get(name, {})
            healthy.append((name, float(stats.get("avg_latency", 999.0))))
        healthy.sort(key=lambda row: row[1])
        return healthy[0][0] if healthy else "groq"

    def mark_result(self, name: str, latency_seconds: float, ok: bool):
        stats = self.provider_health.setdefault(name, {"avg_latency": 999.0, "success": 0.0, "total": 0.0})
        stats["total"] = float(stats.get("total", 0.0)) + 1.0
        if ok:
            stats["success"] = float(stats.get("success", 0.0)) + 1.0
        previous = float(stats.get("avg_latency", 999.0))
        current = max(0.01, float(latency_seconds or 0.01))
        stats["avg_latency"] = round((previous * 0.7) + (current * 0.3), 3)


_provider_manager = AIProviderManager()


def _local_llm_response(messages, system_prompt):
    prompt_parts = [system_prompt, ""]
    for item in messages[-8:]:
        role = item.get("role")
        content = item.get("content")
        if role and content:
            prompt_parts.append(f"{role.upper()}: {content}")
    prompt_parts.append("ASSISTANT:")
    prompt = "\n".join(prompt_parts)
    try:
        response = requests.post(
            _provider_manager.local_ollama_url,
            json={"model": _provider_manager.local_ollama_model, "prompt": prompt, "stream": False},
            timeout=25,
        )
        if response.status_code != 200:
            return None
        data = response.json()
        text = str(data.get("response") or "").strip()
        return text or None
    except Exception:
        return None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "Data"
CONV_DIR = DATA_DIR / "conversations"

CONTACTS_FILE = CONV_DIR / "contacts.json"
TASKS_FILE = CONV_DIR / "tasks.json"
MEMORY_FILE = CONV_DIR / "memory.json"
CHAT_HISTORY_FILE = CONV_DIR / "chat_history.json"
COMMAND_HISTORY_FILE = CONV_DIR / "command_history.json"
LEGACY_CHATLOG_FILE = DATA_DIR / "Chatlog.json"


def _load_json(path: Path, default):
    return load_json(path, default)


def _save_json(path: Path, data):
    save_json(path, data)


def _normalize_user(name: str) -> str:
    return (name or "").strip().lower()


def _normalize_contact_name(name: str) -> str:
    return (name or "").strip().lower()


def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _sync_legacy_chatlog(messages: List[Dict[str, str]]):
    legacy = []
    for item in messages[-MAX_LEGACY_SYNC_MESSAGES:]:
        role = item.get("role", "")
        content = item.get("content", "")
        if role in {"user", "assistant"} and content:
            legacy.append({"role": role, "content": content})
    _save_json(LEGACY_CHATLOG_FILE, legacy)


_groq_client = None
_groq_client_key = ""


def _get_groq_client():
    global _groq_client
    global _groq_client_key
    key = _get_api_key("GROQ_API_KEY", "GroqAPIKey", "GROQAPIKEY")
    if _groq_client is not None and _groq_client_key == key:
        return _groq_client
    if not (Groq and key):
        _groq_client = None
        _groq_client_key = ""
        return None
    try:
        _groq_client = Groq(api_key=key)
        _groq_client_key = key
    except Exception:
        _groq_client = None
        _groq_client_key = ""
    return _groq_client


class ContactManager:
    @staticmethod
    def add_contact(username, name, phone="", email="", messenger="", whatsapp="", instagram=""):
        contacts = _load_json(CONTACTS_FILE, {})
        key = _normalize_contact_name(name)
        if not key:
            return "Invalid contact name"

        if key not in contacts:
            contacts[key] = {}

        if phone and "whatsapp" not in contacts[key]:
            contacts[key]["whatsapp"] = phone
        if email:
            contacts[key]["email"] = email
        if messenger:
            contacts[key]["messenger"] = messenger
        if whatsapp:
            contacts[key]["whatsapp"] = whatsapp
        if instagram:
            contacts[key]["instagram"] = instagram

        _save_json(CONTACTS_FILE, contacts)
        return f"Added contact: {key}"

    @staticmethod
    def get_contact(username, name):
        contacts = _load_json(CONTACTS_FILE, {})
        key = _normalize_contact_name(name)
        value = contacts.get(key)
        if not value:
            return None
        return {
            "username": _normalize_user(username),
            "contact_name": key,
            "data": value,
        }

    @staticmethod
    def get_all_contacts(username):
        contacts = _load_json(CONTACTS_FILE, {})
        rows = []
        for name, mapping in sorted(contacts.items()):
            primary = ""
            if isinstance(mapping, dict):
                primary = mapping.get("whatsapp") or mapping.get("messenger") or mapping.get("instagram") or ""
            rows.append((name, primary))
        return rows


class CommunicationManager:
    @staticmethod
    def log_message(username, contact, channel, message_type, content, status="pending"):
        history = _load_json(COMMAND_HISTORY_FILE, [])
        normalized_channel = (channel or "").strip().lower()
        history.append(
            {
                "time": _now_iso(),
                "kind": "communication",
                "username": _normalize_user(username),
                "contact_name": _normalize_contact_name(contact),
                "channel": normalized_channel,
                # Keep app_name for legacy readers.
                "app_name": normalized_channel,
                "message_type": message_type,
                "message_content": content,
                "status": status,
            }
        )
        _save_json(COMMAND_HISTORY_FILE, history[-500:])
        return f"Message logged: {(content or '')[:20]}..."

    @staticmethod
    def get_channel_config(channel: str) -> dict:
        configs = {
            "whatsapp": {
                "api_key": ConfigManager.get("WHATSAPP_API_KEY"),
                "phone_number_id": ConfigManager.get("WHATSAPP_PHONE_ID", "WHATSAPP_PHONE_NUMBER_ID"),
                "webhook_verify_token": ConfigManager.get("WHATSAPP_WEBHOOK_VERIFY_TOKEN", default="jarvis_verify"),
                "enabled": ConfigManager.get_bool("WHATSAPP_ENABLED", default=False),
            },
            "facebook": {
                "page_access_token": ConfigManager.get("FACEBOOK_PAGE_TOKEN", "FACEBOOK_PAGE_ACCESS_TOKEN"),
                "page_id": ConfigManager.get("FACEBOOK_PAGE_ID"),
                "app_id": ConfigManager.get("FACEBOOK_APP_ID"),
                "app_secret": ConfigManager.get("FACEBOOK_APP_SECRET"),
                "verify_token": ConfigManager.get("FACEBOOK_VERIFY_TOKEN", default="jarvis_fb_verify"),
                "enabled": ConfigManager.get_bool("FACEBOOK_ENABLED", default=False),
            },
            "email": {
                "imap_server": ConfigManager.get("EMAIL_IMAP_SERVER"),
                "imap_port": ConfigManager.get_int("EMAIL_IMAP_PORT", default=993),
                "smtp_server": ConfigManager.get("EMAIL_SMTP_SERVER"),
                "smtp_port": ConfigManager.get_int("EMAIL_SMTP_PORT", default=587),
                "email": ConfigManager.get("EMAIL_ADDRESS"),
                "password": ConfigManager.get("EMAIL_PASSWORD"),
                "check_interval": ConfigManager.get_int("EMAIL_CHECK_INTERVAL", default=60),
                "enabled": ConfigManager.get_bool("EMAIL_ENABLED", default=False),
            },
        }
        return configs.get((channel or "").strip().lower(), {})

    @staticmethod
    def get_pending_messages(username):
        history = _load_json(COMMAND_HISTORY_FILE, [])
        user = _normalize_user(username)
        result = []
        for item in history:
            if item.get("kind") != "communication":
                continue
            if item.get("username") != user:
                continue
            if item.get("status") != "pending":
                continue
            channel = item.get("channel") or item.get("app_name", "")
            result.append((item.get("contact_name", ""), channel, item.get("message_content", "")))
        return result


class MemoryManager:
    @staticmethod
    def remember(username, memory_type, value):
        memory = _load_json(MEMORY_FILE, {})
        key = (memory_type or "").strip().lower()
        if key:
            memory[key] = value
            _save_json(MEMORY_FILE, memory)

    @staticmethod
    def recall(username, memory_type, query_text=None):
        memory = _load_json(MEMORY_FILE, {})
        key = (memory_type or "").strip().lower()
        return memory.get(key)


class TaskHelper:
    @staticmethod
    def add_task(username, task_text, important=2):
        tasks = _load_json(TASKS_FILE, [])
        next_id = (max((item.get("id", 0) for item in tasks), default=0) + 1) if tasks else 1
        tasks.append(
            {
                "id": next_id,
                "task": task_text,
                "important": int(important),
                "done": False,
                "status": "waiting",
                "created_at": _now_iso(),
            }
        )
        _save_json(TASKS_FILE, tasks)
        return f"Added task: {task_text}"

    @staticmethod
    def get_tasks(username, status="waiting"):
        tasks = _load_json(TASKS_FILE, [])
        rows = []
        for item in tasks:
            item_status = item.get("status")
            if not item_status:
                item_status = "done" if item.get("done") else "waiting"
            if item_status != status:
                continue
            rows.append((item.get("task", ""), int(item.get("important", 2))))
        rows.sort(key=lambda x: x[1], reverse=True)
        return rows


def load_chat():
    history = _load_json(CHAT_HISTORY_FILE, [])
    messages = []
    for turn in history[-MAX_CONTEXT_MESSAGES:]:
        user = (turn.get("user") or "").strip()
        assistant = (turn.get("assistant") or "").strip()
        if user:
            messages.append({"role": "user", "content": user})
        if assistant:
            messages.append({"role": "assistant", "content": assistant})
    if not messages:
        legacy = _load_json(LEGACY_CHATLOG_FILE, [])
        for item in legacy[-MAX_CONTEXT_MESSAGES:]:
            role = (item.get("role") or "").strip()
            content = (item.get("content") or item.get("message") or "").strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
    return messages[-MAX_CONTEXT_MESSAGES:]


def save_chat(messages):
    compact = [m for m in messages if m.get("role") in {"user", "assistant"} and m.get("content")]
    compact = compact[-MAX_CONTEXT_MESSAGES:]

    turns = []
    i = 0
    while i < len(compact):
        role = compact[i]["role"]
        content = compact[i]["content"]
        if role == "user":
            assistant_content = ""
            if i + 1 < len(compact) and compact[i + 1]["role"] == "assistant":
                assistant_content = compact[i + 1]["content"]
                i += 1
            turns.append({"time": _now_iso(), "user": content, "assistant": assistant_content})
        else:
            turns.append({"time": _now_iso(), "user": "", "assistant": content})
        i += 1

    existing = _load_json(CHAT_HISTORY_FILE, [])
    merged = (existing + turns)[-MAX_HISTORY_TURNS:]
    _save_json(CHAT_HISTORY_FILE, merged)
    _sync_legacy_chatlog(compact)


def get_time_now():
    now = datetime.datetime.now()
    return {
        "time": now.strftime("%I:%M %p"),
        "date": now.strftime("%A, %B %d, %Y"),
        "hour": now.hour,
        "time_of_day": "morning" if 5 <= now.hour < 12 else "afternoon" if 12 <= now.hour < 17 else "evening",
    }


def detect_communication_command(text):
    source = (text or "").lower()

    message_patterns = [
        r"send message to (.+?) on (.+?) saying (.+)",
        r"send message to (.+?) on (.+?)",
        r"message (.+?) on (.+?)",
        r"text (.+?) on (.+?)",
    ]

    call_patterns = [
        r"call (.+?) on (.+?)",
        r"video call (.+?)",
        r"voice call (.+?)",
        r"ring (.+?) on (.+?)",
    ]

    contact_patterns = [
        r"add contact (.+?)",
        r"save contact (.+?)",
        r"show my contacts",
        r"list contacts",
    ]

    for pattern in message_patterns:
        match = re.search(pattern, source)
        if match:
            return {"type": "send_message", "matches": match.groups()}

    for pattern in call_patterns:
        match = re.search(pattern, source)
        if match:
            return {"type": "make_call", "matches": match.groups()}

    for pattern in contact_patterns:
        match = re.search(pattern, source)
        if match:
            groups = match.groups()
            if groups:
                return {"type": "manage_contacts", "matches": groups}
            return {"type": "manage_contacts", "matches": ("list",)}

    return None


def process_communication_command(command_type, matches, username):
    if command_type == "send_message":
        if len(matches) >= 2:
            contact_name = matches[0]
            app_name = matches[1]
            message_content = matches[2] if len(matches) > 2 else "Hello from Jarvis!"
            CommunicationManager.log_message(username, contact_name, app_name, "text_message", message_content, "pending")
            return f" Message ready to send to {contact_name} on {app_name}: '{message_content}'"

    elif command_type == "make_call":
        contact_name = matches[0]
        app_name = matches[1] if len(matches) > 1 else "phone"
        return f" Call ready to {contact_name} on {app_name}"

    elif command_type == "manage_contacts":
        action = matches[0] if matches else "list"
        if "show" in action or "list" in action:
            contacts = ContactManager.get_all_contacts(username)
            if contacts:
                rows = "\n".join([f"• {name} - {value}" for name, value in contacts])
                return f" Your Contacts:\n{rows}"
            return "No contacts saved yet. Use 'add contact [name]' to save someone."
        ContactManager.add_contact(username, action)
        return f" Contact '{action}' added!"

    return "Communication command processed"


def jarvis_introduction():
    intro = (
        f"I am {_assistant_name()}, your assistant. "
        "I can chat, help with contacts/messages, and support tasks and memory."
    )
    messages = load_chat()
    messages.append({"role": "user", "content": "introduce yourself"})
    messages.append({"role": "assistant", "content": intro})
    save_chat(messages)
    return intro


def is_hello(message):
    hellos = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
    low = (message or "").lower()
    return any(hello in low for hello in hellos)


def is_asking_about_me(message):
    asks = ["introduce yourself", "who are you", "what are you", "tell me about yourself"]
    low = (message or "").lower()
    return any(ask in low for ask in asks)


def get_hello_response():
    time_info = get_time_now()
    return f"Good {time_info['time_of_day']} {_username()}! How can I help?"


def use_deepseek_api(messages, system_prompt):
    api_key = _get_api_key("DEEPSEEK_API_KEY", "DeepSeek_API_KEY", "DeepSeekAPIKey")
    if not api_key:
        return None
    if not _deepseek_breaker.allow():
        return None
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "temperature": 0.7,
            "max_tokens": 1200,
            "stream": False,
        }
        def _op():
            try:
                return requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=30)
            except requests.RequestException as exc:
                raise ServiceRequestError(str(exc)) from exc

        response = retry_with_backoff(_op, retries=2)
        validate_http_status(response.status_code, "deepseek")
        data = response.json()
        _deepseek_breaker.record_success()
        return data.get("choices", [{}])[0].get("message", {}).get("content")
    except ServiceAuthError as exc:
        logger.warning("DeepSeek auth issue: %s", exc)
        _deepseek_breaker.record_failure()
        return None
    except ServiceError:
        _deepseek_breaker.record_failure()
        return None
    except Exception as exc:
        logger.debug("DeepSeek unexpected failure: %s", exc)
        _deepseek_breaker.record_failure()
        return None


def use_xai_api(messages, system_prompt):
    api_key = _get_api_key("XAI_API_KEY", "xAI_API_KEY", "X_AI_API_KEY")
    if not api_key:
        return None
    if not _xai_breaker.allow():
        return None
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "grok-beta",
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "temperature": 0.7,
            "max_tokens": 1000,
            "stream": False,
        }
        def _op():
            try:
                return requests.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload, timeout=30)
            except requests.RequestException as exc:
                raise ServiceRequestError(str(exc)) from exc

        response = retry_with_backoff(_op, retries=2)
        validate_http_status(response.status_code, "xai")
        data = response.json()
        _xai_breaker.record_success()
        return data.get("choices", [{}])[0].get("message", {}).get("content")
    except ServiceAuthError as exc:
        logger.warning("xAI auth issue: %s", exc)
        _xai_breaker.record_failure()
        return None
    except ServiceError:
        _xai_breaker.record_failure()
        return None
    except Exception as exc:
        logger.debug("xAI unexpected failure: %s", exc)
        _xai_breaker.record_failure()
        return None


def _groq_response(messages, system_prompt):
    groq_client = _get_groq_client()
    if not groq_client:
        return None
    if not _groq_breaker.allow():
        return None

    models = ["llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"]
    for model in models:
        try:
            completion = groq_client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                max_tokens=800,
                temperature=0.7,
                top_p=0.9,
                stream=False,
            )
            text = completion.choices[0].message.content
            if text:
                _groq_breaker.record_success()
                return text.strip()
        except Exception:
            continue

    _groq_breaker.record_failure()

    return None


def _iter_sse_tokens(response):
    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if payload == "[DONE]":
            break
        try:
            data = json.loads(payload)
        except Exception:
            continue
        delta = data.get("choices", [{}])[0].get("delta", {})
        token = delta.get("content")
        if token:
            yield token


def _stream_openai(messages, system_prompt):
    api_key = _get_api_key("OPENAI_API_KEY", "OPENAIAPIKEY", "OPEN_AI_API_KEY")
    if not api_key:
        return None
    if not _openai_stream_breaker.allow():
        return None
    try:
        def _op():
            try:
                return requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": os.getenv("JARVIS_STREAM_MODEL", "gpt-4o-mini"),
                        "messages": [{"role": "system", "content": system_prompt}] + messages,
                        "temperature": 0.6,
                        "stream": True,
                    },
                    stream=True,
                    timeout=60,
                )
            except requests.RequestException as exc:
                raise ServiceRequestError(str(exc)) from exc

        response = retry_with_backoff(_op, retries=2)
        validate_http_status(response.status_code, "openai-stream")
        _openai_stream_breaker.record_success()
        return _iter_sse_tokens(response)
    except ServiceAuthError as exc:
        logger.warning("OpenAI stream auth issue: %s", exc)
        _openai_stream_breaker.record_failure()
        return None
    except ServiceError:
        _openai_stream_breaker.record_failure()
        return None
    except Exception as exc:
        logger.debug("OpenAI stream unexpected failure: %s", exc)
        _openai_stream_breaker.record_failure()
        return None


def _stream_deepseek(messages, system_prompt):
    api_key = _get_api_key("DEEPSEEK_API_KEY", "DeepSeek_API_KEY", "DeepSeekAPIKey")
    if not api_key:
        return None
    if not _deepseek_stream_breaker.allow():
        return None
    try:
        def _op():
            try:
                return requests.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "system", "content": system_prompt}] + messages,
                        "temperature": 0.6,
                        "stream": True,
                    },
                    stream=True,
                    timeout=60,
                )
            except requests.RequestException as exc:
                raise ServiceRequestError(str(exc)) from exc

        response = retry_with_backoff(_op, retries=2)
        validate_http_status(response.status_code, "deepseek-stream")
        _deepseek_stream_breaker.record_success()
        return _iter_sse_tokens(response)
    except ServiceAuthError as exc:
        logger.warning("DeepSeek stream auth issue: %s", exc)
        _deepseek_stream_breaker.record_failure()
        return None
    except ServiceError:
        _deepseek_stream_breaker.record_failure()
        return None
    except Exception as exc:
        logger.debug("DeepSeek stream unexpected failure: %s", exc)
        _deepseek_stream_breaker.record_failure()
        return None


def _stream_xai(messages, system_prompt):
    api_key = _get_api_key("XAI_API_KEY", "xAI_API_KEY", "X_AI_API_KEY")
    if not api_key:
        return None
    if not _xai_stream_breaker.allow():
        return None
    try:
        def _op():
            try:
                return requests.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "grok-beta",
                        "messages": [{"role": "system", "content": system_prompt}] + messages,
                        "temperature": 0.6,
                        "stream": True,
                    },
                    stream=True,
                    timeout=60,
                )
            except requests.RequestException as exc:
                raise ServiceRequestError(str(exc)) from exc

        response = retry_with_backoff(_op, retries=2)
        validate_http_status(response.status_code, "xai-stream")
        _xai_stream_breaker.record_success()
        return _iter_sse_tokens(response)
    except ServiceAuthError as exc:
        logger.warning("xAI stream auth issue: %s", exc)
        _xai_stream_breaker.record_failure()
        return None
    except ServiceError:
        _xai_stream_breaker.record_failure()
        return None
    except Exception as exc:
        logger.debug("xAI stream unexpected failure: %s", exc)
        _xai_stream_breaker.record_failure()
        return None


def get_context(window: int = CONTEXT_WINDOW):
    messages = load_chat()
    turns = min(MAX_CONTEXT_MESSAGES, max(2, int(window) * 2))
    return messages[-turns:]


def process_incremental(partial_input: str) -> str:
    clean = (partial_input or "").strip()
    if not clean:
        return ""
    if clean.endswith((".", "?", "!")):
        return clean
    return ""


def stream_response(user_input: str) -> Generator[str, None, None]:
    """Yield response tokens when possible.

    If streaming providers are unavailable, this yields one full fallback chunk from
    ``SmartChatBot`` so callers can handle mixed streaming/non-streaming behavior.
    """
    text = (user_input or "").strip()
    if not text:
        yield "Please say something."
        return

    messages = get_context()

    comm_command = detect_communication_command(text)
    if comm_command:
        response = process_communication_command(comm_command["type"], comm_command["matches"], _username())
        messages.append({"role": "user", "content": text})
        messages.append({"role": "assistant", "content": response})
        save_chat(messages)
        yield response
        return

    if is_hello(text):
        response = get_hello_response()
        messages.append({"role": "user", "content": text})
        messages.append({"role": "assistant", "content": response})
        save_chat(messages)
        yield response
        return

    if is_asking_about_me(text):
        response = jarvis_introduction()
        yield response
        return

    messages.append({"role": "user", "content": text})
    time_info = get_time_now()
    system_prompt = (
        f"You are {_assistant_name()}, a concise, helpful assistant. "
        f"Current time: {time_info['time']} on {time_info['date']}. "
        f"User: {_username()}."
    )

    provider_stream = None
    ordered = [_provider_manager.get_best_provider("stream"), "openai", "deepseek", "xai"]
    seen = set()
    for provider in ordered:
        if provider in seen:
            continue
        seen.add(provider)
        started = datetime.datetime.now().timestamp()
        stream_obj = None
        if provider == "openai":
            stream_obj = _stream_openai(messages, system_prompt)
        elif provider == "deepseek":
            stream_obj = _stream_deepseek(messages, system_prompt)
        elif provider == "xai":
            stream_obj = _stream_xai(messages, system_prompt)
        else:
            continue
        ok = stream_obj is not None
        _provider_manager.mark_result(provider, datetime.datetime.now().timestamp() - started, ok)
        if ok:
            provider_stream = stream_obj
            break

    if provider_stream is None:
        logger.warning("Streaming providers unavailable; falling back to non-stream SmartChatBot response")
        fallback = SmartChatBot(text)
        yield fallback
        return

    final_response = ""
    try:
        for token in provider_stream:
            final_response += token
            yield token
    except Exception as exc:
        logger.warning("Streaming provider aborted mid-response: %s", exc)

    final_response = final_response.strip() or "I can still help with local commands, tasks, contacts, and memory."
    messages.append({"role": "assistant", "content": final_response})
    save_chat(messages)
    return


def SmartChatBot(user_input):
    try:
        text = (user_input or "").strip()
        if not text:
            return "Please say something."

        messages = load_chat()

        comm_command = detect_communication_command(text)
        if comm_command:
            response = process_communication_command(comm_command["type"], comm_command["matches"], _username())
            messages.append({"role": "user", "content": text})
            messages.append({"role": "assistant", "content": response})
            save_chat(messages)
            return response

        if is_hello(text):
            response = get_hello_response()
            messages.append({"role": "user", "content": text})
            messages.append({"role": "assistant", "content": response})
            save_chat(messages)
            return response

        if is_asking_about_me(text):
            return jarvis_introduction()

        messages.append({"role": "user", "content": text})
        time_info = get_time_now()
        system_prompt = (
            f"You are {_assistant_name()}, a concise, helpful assistant. "
            f"Current time: {time_info['time']} on {time_info['date']}. "
            f"User: {_username()}."
        )

        provider_order = [_provider_manager.get_best_provider("chat"), "deepseek", "xai", "groq", "local"]
        response = None
        used = None
        seen = set()
        for provider in provider_order:
            if provider in seen:
                continue
            seen.add(provider)
            started = datetime.datetime.now().timestamp()
            if provider == "deepseek":
                candidate = use_deepseek_api(messages, system_prompt)
            elif provider == "xai":
                candidate = use_xai_api(messages, system_prompt)
            elif provider == "groq":
                candidate = _groq_response(messages, system_prompt)
            elif provider == "local":
                candidate = _local_llm_response(messages, system_prompt)
            else:
                candidate = None

            ok = bool(candidate)
            _provider_manager.mark_result(provider, datetime.datetime.now().timestamp() - started, ok)
            if ok:
                response = candidate
                used = provider
                break

        if not response:
            response = "I can still help with local commands, tasks, contacts, and memory."
        elif used:
            logger.debug("SmartChatBot provider selected: %s", used)

        messages.append({"role": "assistant", "content": response})
        save_chat(messages)
        return response
    except Exception as exc:
        return f"Something went wrong: {exc}"


def show_status():
    messages = load_chat()
    contacts = ContactManager.get_all_contacts(_username())
    pending = CommunicationManager.get_pending_messages(_username())

    print("\n System Status:")
    print(f"  Assistant: {_assistant_name()}")
    print(f"  User: {_username()}")
    print(f"  Messages in memory: {len(messages)}")
    print(f"  Contacts saved: {len(contacts)}")
    print(f"  Pending messages: {len(pending)}")
    print(
        "  APIs Available: "
        f"Groq {'OK' if bool(_get_api_key('GROQ_API_KEY', 'GroqAPIKey', 'GROQAPIKEY')) else 'MISSING'}, "
        f"DeepSeek {'OK' if bool(_get_api_key('DEEPSEEK_API_KEY', 'DeepSeek_API_KEY', 'DeepSeekAPIKey')) else 'MISSING'}, "
        f"xAI {'OK' if bool(_get_api_key('XAI_API_KEY', 'xAI_API_KEY', 'X_AI_API_KEY')) else 'MISSING'}"
    )


if __name__ == "__main__":
    print(f"\n{_assistant_name()} Communication Assistant")
    print("=" * 50)
    show_status()
    print("=" * 50)
    print("Type 'exit' to quit")

    while True:
        try:
            user_input = input(f"\n{_username()}: ").strip()
            if user_input.lower() in ["exit", "quit", "bye"]:
                print(f"\n{_assistant_name()}: Goodbye {_username()}!")
                break
            if user_input.lower() == "status":
                show_status()
                continue
            if not user_input:
                continue
            response = SmartChatBot(user_input)
            print(f"\n{_assistant_name()}: {response}")
        except KeyboardInterrupt:
            print(f"\n{_assistant_name()}: Stopping...")
            break
        except Exception as e:
            print(f"\n{_assistant_name()}: Error: {e}")
