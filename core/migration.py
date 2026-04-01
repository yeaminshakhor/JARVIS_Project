import sqlite3
from pathlib import Path
from datetime import datetime

from .utils import load_json, save_json


def _normalize_name(name: str):
    return (name or "").strip().lower()


def migrate_legacy_data(project_root: Path | None = None):
    root = Path(project_root).resolve() if project_root else Path(__file__).resolve().parents[1]
    data_dir = root / "Data"
    conv_dir = data_dir / "conversations"
    conv_dir.mkdir(parents=True, exist_ok=True)

    contacts_file = conv_dir / "contacts.json"
    tasks_file = conv_dir / "tasks.json"
    memory_file = conv_dir / "memory.json"
    chat_history_file = conv_dir / "chat_history.json"

    contacts = load_json(contacts_file, {})
    tasks = load_json(tasks_file, [])
    memory = load_json(memory_file, {})
    chat_history = load_json(chat_history_file, [])
    contacts_changed = False
    tasks_changed = False
    memory_changed = False
    chat_changed = False

    summary = {
        "contacts": 0,
        "tasks": 0,
        "memory": 0,
        "chat_turns": 0,
        "source": [],
    }

    sqlite_path = data_dir / "memory.db"
    if sqlite_path.exists():
        try:
            conn = sqlite3.connect(str(sqlite_path))
            cur = conn.cursor()

            cur.execute(
                """
                SELECT contact_name, phone_number, messenger_id, whatsapp_id, instagram_id
                FROM user_contacts
                """
            )
            for row in cur.fetchall():
                contact_name, phone, messenger, whatsapp, instagram = row
                name_key = _normalize_name(contact_name)
                if not name_key:
                    continue
                if name_key not in contacts:
                    contacts[name_key] = {}

                if whatsapp:
                    contacts[name_key]["whatsapp"] = whatsapp
                    contacts_changed = True
                elif phone and "whatsapp" not in contacts[name_key]:
                    contacts[name_key]["whatsapp"] = phone
                    contacts_changed = True

                if messenger:
                    contacts[name_key]["messenger"] = messenger
                    contacts_changed = True
                if instagram:
                    contacts[name_key]["instagram"] = instagram
                    contacts_changed = True

                summary["contacts"] += 1

            next_id = (max((item.get("id", 0) for item in tasks), default=0) + 1) if tasks else 1
            cur.execute("SELECT task, status, created_time FROM user_tasks")
            for task_text, status, created_time in cur.fetchall():
                clean_task = (task_text or "").strip()
                if not clean_task:
                    continue
                if any((item.get("task") or "").strip().lower() == clean_task.lower() for item in tasks):
                    continue

                done = str(status or "").lower() in {"done", "completed", "complete"}
                tasks.append(
                    {
                        "id": next_id,
                        "task": clean_task,
                        "done": done,
                        "created_at": (created_time or datetime.now().isoformat())[:19],
                    }
                )
                next_id += 1
                summary["tasks"] += 1
                tasks_changed = True

            cur.execute("SELECT memory_type, memory_value FROM user_memory")
            for memory_type, memory_value in cur.fetchall():
                key = _normalize_name(memory_type)
                value = (memory_value or "").strip()
                if not key or not value:
                    continue
                if key not in memory:
                    memory[key] = value
                    summary["memory"] += 1
                    memory_changed = True

            conn.close()
            summary["source"].append("memory.db")
        except Exception:
            pass

    chatlog_path = data_dir / "Chatlog.json"
    if chatlog_path.exists():
        legacy_messages = load_json(chatlog_path, [])
        for item in legacy_messages:
            role = (item.get("role") or "").strip().lower()
            content = (item.get("content") or item.get("message") or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            chat_history.append(
                {
                    "time": datetime.now().isoformat(timespec="seconds"),
                    "user": content if role == "user" else "",
                    "assistant": content if role == "assistant" else "",
                }
            )
            summary["chat_turns"] += 1
            chat_changed = True

        if legacy_messages:
            summary["source"].append("Chatlog.json")

    if len(chat_history) > 200:
        chat_history = chat_history[-200:]
        chat_changed = True

    if contacts_changed:
        save_json(contacts_file, contacts)
    if tasks_changed:
        save_json(tasks_file, tasks)
    if memory_changed:
        save_json(memory_file, memory)
    if chat_changed:
        save_json(chat_history_file, chat_history)

    return summary


def render_migration_summary(summary: dict):
    if not summary:
        return ""

    moved = summary.get("contacts", 0) + summary.get("tasks", 0) + summary.get("memory", 0) + summary.get("chat_turns", 0)
    if moved == 0:
        return ""

    sources = ", ".join(summary.get("source", [])) or "legacy stores"
    return (
        "Migration completed | "
        f"contacts:{summary.get('contacts', 0)} "
        f"tasks:{summary.get('tasks', 0)} "
        f"memory:{summary.get('memory', 0)} "
        f"chat_turns:{summary.get('chat_turns', 0)} "
        f"from {sources}"
    )
