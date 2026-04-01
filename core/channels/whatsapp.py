"""WhatsApp Business API integration for JARVIS."""

from __future__ import annotations

from typing import Any, Dict, Optional

# Direct script execution breaks package-relative imports.
if __name__ == "__main__" and (not __package__):
    raise SystemExit("Run this module as: python -m core.channels.whatsapp")

import requests

from ..channel_manager import BaseChannel


class WhatsAppChannel(BaseChannel):
    """WhatsApp Business API channel adapter."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("whatsapp", config)
        self.api_key = config.get("api_key")
        self.phone_number_id = config.get("phone_number_id")
        self.webhook_verify_token = config.get("webhook_verify_token", "jarvis_verify")
        self.base_url = "https://graph.facebook.com/v18.0"

    def send(self, message: str, recipient: Optional[str] = None) -> bool:
        if not recipient:
            self.logger.error("No recipient specified for WhatsApp message")
            return False
        if not self.api_key or not self.phone_number_id:
            self.logger.error("WhatsApp API credentials are missing")
            return False

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"body": message},
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            if response.status_code == 200:
                self.logger.info("WhatsApp message sent to %s", recipient)
                return True
            self.logger.error("WhatsApp API error: %s", response.text)
            return False
        except Exception as exc:
            self.logger.error("WhatsApp send failed: %s", exc)
            return False

    def verify_webhook(self, request_args: Dict[str, str]) -> Optional[str]:
        mode = request_args.get("hub.mode")
        token = request_args.get("hub.verify_token")
        challenge = request_args.get("hub.challenge")

        if mode and token and mode == "subscribe" and token == self.webhook_verify_token:
            return challenge
        return None

    def handle_webhook(self, data: Dict[str, Any]) -> None:
        try:
            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    for msg in messages:
                        if msg.get("type") == "text":
                            self.receive(
                                {
                                    "text": msg.get("text", {}).get("body", ""),
                                    "sender": msg.get("from"),
                                    "recipient": value.get("metadata", {}).get("display_phone_number"),
                                    "message_id": msg.get("id"),
                                    "timestamp": msg.get("timestamp"),
                                }
                            )
        except Exception as exc:
            self.logger.error("Error processing WhatsApp webhook: %s", exc)
