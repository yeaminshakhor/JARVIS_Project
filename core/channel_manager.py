"""Unified channel manager for cross-platform messaging integrations.

This module provides a shared message queue and channel abstraction that lets
JARVIS send and receive messages through multiple providers (WhatsApp,
Facebook Messenger, Email, etc.) with a single interface.
"""

from __future__ import annotations

import logging
import queue
import threading
from datetime import datetime
from typing import Any, Dict, Optional


class ChannelManager:
    """Manages multiple messaging channels with a unified interface."""

    def __init__(self):
        self.channels: Dict[str, BaseChannel] = {}
        self.message_queue: queue.Queue[Dict[str, Any]] = queue.Queue()
        self.logger = logging.getLogger(__name__)
        self.running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._assistant = None

    def register_channel(self, name: str, channel: "BaseChannel") -> None:
        """Register a messaging channel instance under a unique name."""
        self.channels[name] = channel
        self.logger.info("Registered channel: %s", name)

    def start(self) -> None:
        """Start all registered channels and the inbound message worker."""
        if self.running:
            return

        self.running = True
        for name, channel in self.channels.items():
            try:
                channel.start()
                self.logger.info("Started channel: %s", name)
            except Exception as exc:
                self.logger.error("Failed to start %s: %s", name, exc)

        self._worker_thread = threading.Thread(target=self._process_messages, daemon=True)
        self._worker_thread.start()

    def register_from_config(self) -> int:
        """Register enabled channels from CommunicationManager configuration."""
        from core.chatbot import CommunicationManager
        from core.channels.email_channel import EmailChannel
        from core.channels.facebook import FacebookMessengerChannel
        from core.channels.whatsapp import WhatsAppChannel

        created = 0
        channel_builders = {
            "whatsapp": WhatsAppChannel,
            "facebook": FacebookMessengerChannel,
            "email": EmailChannel,
        }

        for name, channel_cls in channel_builders.items():
            if name in self.channels:
                continue
            config = CommunicationManager.get_channel_config(name)
            if not config.get("enabled"):
                continue
            try:
                self.register_channel(name, channel_cls(config))
                created += 1
            except Exception as exc:
                self.logger.error("Failed to register %s from config: %s", name, exc)

        return created

    def stop(self) -> None:
        """Stop all channels and message processing."""
        self.running = False

        for channel in self.channels.values():
            try:
                channel.stop()
            except Exception as exc:
                self.logger.error("Error stopping channel: %s", exc)

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2)

    def broadcast(self, message: str, channels: Optional[list[str]] = None) -> None:
        """Send a message to specific channels, or all channels when omitted."""
        targets = channels or list(self.channels.keys())
        for name in targets:
            channel = self.channels.get(name)
            if not channel:
                continue
            try:
                channel.send(message)
            except Exception as exc:
                self.logger.error("Broadcast failed for %s: %s", name, exc)

    def _process_messages(self) -> None:
        """Pull inbound messages from all channels and route to JARVIS."""
        while self.running:
            try:
                msg = self.message_queue.get(timeout=1)
                self._handle_incoming(msg)
            except queue.Empty:
                continue
            except Exception as exc:
                self.logger.error("Message processing error: %s", exc)

    def _get_assistant(self):
        if self._assistant is None:
            from core.safe_control import SafeControlAssistant

            self._assistant = SafeControlAssistant()
        return self._assistant

    def _handle_incoming(self, message: Dict[str, Any]) -> None:
        """Route an inbound message to JARVIS and send a channel response."""
        text = str(message.get("text", "")).strip()
        if not text:
            return

        assistant = self._get_assistant()
        response = assistant.process(text)

        origin = str(message.get("channel", "")).strip().lower()
        channel = self.channels.get(origin)
        if channel and response:
            channel.send(str(response), message.get("sender") or message.get("recipient"))


class BaseChannel:
    """Base class for all channel adapters."""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"channel.{name}")
        self.running = False

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def send(self, message: str, recipient: Optional[str] = None) -> bool:
        raise NotImplementedError

    def receive(self, message: Dict[str, Any]) -> None:
        channel_manager.message_queue.put(
            {
                "channel": self.name,
                "text": message.get("text", ""),
                "sender": message.get("sender"),
                "recipient": message.get("recipient"),
                "timestamp": message.get("timestamp") or datetime.now().isoformat(),
            }
        )


# Shared singleton used by channel implementations.
channel_manager = ChannelManager()
