"""Messaging channel adapters for JARVIS."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .email_channel import EmailChannel
    from .facebook import FacebookMessengerChannel
    from .whatsapp import WhatsAppChannel


def __getattr__(name: str):
    if name == "EmailChannel":
        from .email_channel import EmailChannel

        return EmailChannel
    if name == "FacebookMessengerChannel":
        from .facebook import FacebookMessengerChannel

        return FacebookMessengerChannel
    if name == "WhatsAppChannel":
        from .whatsapp import WhatsAppChannel

        return WhatsAppChannel
    raise AttributeError(name)

__all__ = [
    "EmailChannel",
    "FacebookMessengerChannel",
    "WhatsAppChannel",
]
