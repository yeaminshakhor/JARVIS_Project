from __future__ import annotations

import logging
import importlib
from typing import Any, Dict

from .channel_manager import channel_manager
from .chatbot import CommunicationManager
from .channels.facebook import FacebookMessengerChannel
from .channels.whatsapp import WhatsAppChannel

logger = logging.getLogger(__name__)


def _whatsapp_channel() -> WhatsAppChannel:
    return WhatsAppChannel(CommunicationManager.get_channel_config("whatsapp"))


def _facebook_channel() -> FacebookMessengerChannel:
    return FacebookMessengerChannel(CommunicationManager.get_channel_config("facebook"))


def register_fastapi_routes(app) -> None:
    """Register webhook routes on a FastAPI app instance."""

    @app.get("/webhooks/whatsapp")
    def whatsapp_verify(hub_mode: str = "", hub_verify_token: str = "", hub_challenge: str = ""):
        channel = _whatsapp_channel()
        challenge = channel.verify_webhook(
            {
                "hub.mode": hub_mode,
                "hub.verify_token": hub_verify_token,
                "hub.challenge": hub_challenge,
            }
        )
        if challenge is None:
            return {"ok": False, "error": "verification failed"}
        return {"ok": True, "challenge": challenge}

    @app.post("/webhooks/whatsapp")
    async def whatsapp_webhook(payload: Dict[str, Any]):
        _whatsapp_channel().handle_webhook(payload)
        return {"ok": True}

    @app.get("/webhooks/facebook")
    def facebook_verify(hub_mode: str = "", hub_verify_token: str = "", hub_challenge: str = ""):
        verify_token = CommunicationManager.get_channel_config("facebook").get("verify_token", "jarvis_fb_verify")
        ok = bool(hub_mode == "subscribe" and hub_verify_token == verify_token)
        if not ok:
            return {"ok": False, "error": "verification failed"}
        return {"ok": True, "challenge": hub_challenge}

    @app.post("/webhooks/facebook")
    async def facebook_webhook(payload: Dict[str, Any]):
        _facebook_channel().handle_webhook(payload)
        return {"ok": True}


def register_flask_routes(app) -> None:
    """Register webhook routes on a Flask app instance."""

    flask_mod = importlib.import_module("flask")
    jsonify = flask_mod.jsonify
    request = flask_mod.request

    @app.get("/webhooks/whatsapp")
    def whatsapp_verify():
        channel = _whatsapp_channel()
        challenge = channel.verify_webhook(request.args.to_dict(flat=True))
        if challenge is None:
            return jsonify({"ok": False, "error": "verification failed"}), 403
        return str(challenge), 200

    @app.post("/webhooks/whatsapp")
    def whatsapp_webhook():
        payload = request.get_json(silent=True) or {}
        _whatsapp_channel().handle_webhook(payload)
        return jsonify({"ok": True}), 200

    @app.get("/webhooks/facebook")
    def facebook_verify():
        verify_token = CommunicationManager.get_channel_config("facebook").get("verify_token", "jarvis_fb_verify")
        mode = request.args.get("hub.mode", "")
        token = request.args.get("hub.verify_token", "")
        challenge = request.args.get("hub.challenge", "")
        if mode == "subscribe" and token == verify_token:
            return str(challenge), 200
        return jsonify({"ok": False, "error": "verification failed"}), 403

    @app.post("/webhooks/facebook")
    def facebook_webhook():
        payload = request.get_json(silent=True) or {}
        _facebook_channel().handle_webhook(payload)
        return jsonify({"ok": True}), 200


def create_fastapi_app():
    """Create a FastAPI app with webhook routes registered."""
    try:
        fastapi_mod = importlib.import_module("fastapi")
        FastAPI = fastapi_mod.FastAPI
    except Exception as exc:
        raise RuntimeError("FastAPI is not installed") from exc

    app = FastAPI(title="JARVIS Channel Webhooks")
    register_fastapi_routes(app)
    return app


def create_flask_app():
    """Create a Flask app with webhook routes registered."""
    try:
        flask_mod = importlib.import_module("flask")
        Flask = flask_mod.Flask
    except Exception as exc:
        raise RuntimeError("Flask is not installed") from exc

    app = Flask("jarvis_channel_webhooks")
    register_flask_routes(app)
    return app


def ensure_channels_registered() -> int:
    """Ensure enabled channels are registered before webhook handling starts."""
    return channel_manager.register_from_config()
