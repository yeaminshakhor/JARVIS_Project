"""Contact management service."""

from __future__ import annotations

import re
from typing import Callable, Dict

from .constants import SUPPORTED_SOCIAL_PLATFORMS


class ContactService:
    def __init__(self, contacts: Dict[str, Dict[str, str]], save_callback: Callable[[], None]):
        self._contacts = contacts
        self._save = save_callback
        self._platform_pattern = "|".join(sorted(SUPPORTED_SOCIAL_PLATFORMS))

    def add_contact_command(self, payload: str) -> str:
        match = re.match(rf"^(.+?)\s+on\s+({self._platform_pattern})\s+(.+)$", payload, re.IGNORECASE)
        if not match:
            return "Usage: add contact <name> on <platform> <handle>"

        name = match.group(1).strip().lower()
        platform = match.group(2).strip().lower()
        handle = match.group(3).strip()

        if name not in self._contacts:
            self._contacts[name] = {}
        self._contacts[name][platform] = handle
        self._save()
        return f"Saved contact {name} on {platform}"

    def list_contacts(self) -> str:
        if not self._contacts:
            return "No contacts saved"
        lines = ["Contacts"]
        for name, mapping in sorted(self._contacts.items()):
            details = ", ".join(f"{k}:{v}" for k, v in sorted(mapping.items()))
            lines.append(f"- {name}: {details}")
        return "\n".join(lines)

    def resolve_contact_handle(self, person: str, platform: str):
        name = (person or "").strip().lower()
        channel = (platform or "").strip().lower()
        if name in self._contacts and channel in self._contacts[name]:
            return self._contacts[name][channel]
        return None

    def send_message_shortcut(self, payload: str, sender: Callable[[str, str, str], str]) -> str:
        tokens = payload.split()
        if not tokens:
            return "Usage: send message <platform> <person> [message]"

        first = tokens[0].lower()
        if first in SUPPORTED_SOCIAL_PLATFORMS:
            if len(tokens) < 2:
                return "Usage: send message <platform> <person> [message]"
            platform = first
            person = tokens[1].lower()
            message = " ".join(tokens[2:]).strip()
            return sender(platform, person, message)

        person = first
        message = " ".join(tokens[1:]).strip()
        return sender("whatsapp", person, message)
