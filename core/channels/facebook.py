"""Facebook Messenger Graph API integration for JARVIS."""

from __future__ import annotations

from typing import Any, Dict, Optional

# Direct script execution breaks package-relative imports.
if __name__ == "__main__" and (not __package__):
    raise SystemExit("Run this module as: python -m core.channels.facebook")

import requests

from ..channel_manager import BaseChannel


class FacebookMessengerChannel(BaseChannel):
    """Facebook Messenger channel adapter with webhook support."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__("facebook", config)
        self.page_access_token = config.get("page_access_token")
        self.page_id = config.get("page_id")
        self.app_id = config.get("app_id")
        self.app_secret = config.get("app_secret")
        self.verify_token = config.get("verify_token", "jarvis_fb_verify")
        self.base_url = "https://graph.facebook.com/v18.0"

    def send(self, message: str, recipient: Optional[str] = None) -> bool:
        if not recipient:
            self.logger.error("No recipient specified")
            return False
        if not self.page_access_token:
            self.logger.error("Facebook page access token is missing")
            return False

        url = f"{self.base_url}/me/messages"
        params = {"access_token": self.page_access_token}
        data = {
            "recipient": {"id": recipient},
            "message": {"text": message},
        }

        try:
            response = requests.post(url, params=params, json=data, timeout=10)
            if response.status_code == 200:
                self.logger.info("Facebook message sent to %s", recipient)
                return True
            self.logger.error("Facebook API error: %s", response.text)
            return False
        except Exception as exc:
            self.logger.error("Facebook send failed: %s", exc)
            return False

    def handle_webhook(self, data: Dict[str, Any]) -> None:
        try:
            for entry in data.get("entry", []):
                for event in entry.get("messaging", []):
                    message = event.get("message", {})
                    if "text" in message:
                        self.receive(
                            {
                                "text": message.get("text", ""),
                                "sender": event.get("sender", {}).get("id"),
                                "recipient": event.get("recipient", {}).get("id"),
                                "timestamp": event.get("timestamp"),
                            }
                        )
        except Exception as exc:
            self.logger.error("Facebook webhook processing error: %s", exc)
