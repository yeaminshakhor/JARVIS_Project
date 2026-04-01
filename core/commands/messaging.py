"""Messaging service with separate web-mode and API-mode actions."""

from __future__ import annotations

import re
import webbrowser
from typing import Callable
from urllib.parse import quote_plus

from .constants import SUPPORTED_SOCIAL_PLATFORMS


class MessagingService:
    def __init__(self, resolve_handle: Callable[[str, str], str], looks_like_phone: Callable[[str], bool]):
        self._resolve_handle = resolve_handle
        self._looks_like_phone = looks_like_phone

    def build_web_message_action(self, platform: str, person: str, message: str = ""):
        normalized_platform = (platform or "").strip().lower()
        normalized_person = (person or "").strip().lower()
        handle = self._resolve_handle(normalized_person, normalized_platform)
        target = handle or normalized_person
        clean_message = (message or "").strip()

        if normalized_platform in {"facebook", "messenger"}:
            url = f"https://www.facebook.com/messages/t/{quote_plus(target)}"
            return {"ok": True, "url": url, "message": f"Opened {normalized_platform} message page for {normalized_person}"}

        if normalized_platform == "instagram":
            url = "https://www.instagram.com/direct/inbox/"
            return {"ok": True, "url": url, "message": f"Opened instagram message page for {normalized_person}"}

        if normalized_platform == "whatsapp":
            if not handle and not self._looks_like_phone(target):
                return {
                    "ok": False,
                    "fallback_url": "https://web.whatsapp.com",
                    "message": f"Opened WhatsApp. Add contact first: add contact {normalized_person} on whatsapp <phone>",
                }
            if clean_message:
                url = f"https://web.whatsapp.com/send?phone={quote_plus(target)}&text={quote_plus(clean_message)}"
            else:
                url = f"https://web.whatsapp.com/send?phone={quote_plus(target)}"
            return {"ok": True, "url": url, "message": f"Opened whatsapp message page for {normalized_person}"}

        return {"ok": False, "message": "Unsupported platform"}

    def send_message_web(self, platform: str, person: str, message: str = "") -> str:
        action = self.build_web_message_action(platform, person, message)
        if not action["ok"]:
            if action.get("fallback_url"):
                webbrowser.open(action["fallback_url"])
            return action["message"]
        webbrowser.open(action["url"])
        return action["message"]

    def open_call(self, platform: str, person: str, video: bool) -> str:
        channel = (platform or "").strip().lower()
        if channel not in SUPPORTED_SOCIAL_PLATFORMS:
            return "Unsupported platform"

        handle = self._resolve_handle(person, channel)
        target = handle or person

        if channel in {"facebook", "messenger"}:
            url = f"https://www.messenger.com/t/{quote_plus(target)}"
            webbrowser.open(url)
            call_type = "video" if video else "audio"
            return f"Opened Messenger chat for {person}. Start {call_type} call from call button"

        if channel == "instagram":
            webbrowser.open("https://www.instagram.com/direct/inbox/")
            call_type = "video" if video else "audio"
            return f"Opened Instagram inbox. Start {call_type} call to {person} from the chat"

        if channel == "whatsapp":
            url = f"https://web.whatsapp.com/send?phone={quote_plus(target)}"
            webbrowser.open(url)
            call_type = "video" if video else "audio"
            return f"Opened WhatsApp chat for {person}. Start {call_type} call from call button"

        return "Unsupported platform"

    @staticmethod
    def parse_contact_call(payload: str):
        pattern = "|".join(sorted(SUPPORTED_SOCIAL_PLATFORMS))
        return re.match(rf"^(.+?)\s+on\s+({pattern})$", payload, re.IGNORECASE)
