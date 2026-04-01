import os
import json
import logging
import subprocess
import sys
import threading
import time
import webbrowser
import functools
import uuid
import shutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote_plus

import psutil
from dotenv import dotenv_values
from PyQt5.QtCore import QObject, QTimer, QUrl, pyqtSlot
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineSettings, QWebEngineView
from PyQt5.QtWebChannel import QWebChannel

from core.safe_control import SafeControlAssistant
from core.Assistant import EnhancedProfessionalAIAutomation
from core.stt import WorkingSpeechRecognition
from core.tts import speak as tts_speak
from core.conversation_manager import ConversationManager
from core.image_gen import generate_images_with_progress
from core.search import search_with_progress
from core.model import classify_with_confidence
from .monitors import get_system_stats_snapshot


def _assistant_name() -> str:
    try:
        env = dotenv_values(".env")
        return env.get("Assistantname") or env.get("AssistantName") or "JARVIS"
    except Exception:
        return "JARVIS"


def _weather_city() -> str:
    try:
        return dotenv_values(".env").get("WeatherCity", "Dhaka")
    except Exception:
        return "Dhaka"


class GracefulErrorHandler:
    @staticmethod
    def handle_bridge_error(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                logging.error("Bridge error in %s: %s", func.__name__, exc)
                return json.dumps(
                    {
                        "ok": False,
                        "message": f"Service temporarily unavailable: {str(exc)}",
                        "fallback": True,
                    }
                )

        return wrapper

    @staticmethod
    def with_fallback(primary_func, fallback_func):
        try:
            return primary_func()
        except Exception as exc:
            logging.warning("Primary failed, using fallback: %s", exc)
            try:
                return fallback_func()
            except Exception as exc2:
                logging.error("Fallback also failed: %s", exc2)
                return None


class ExternalBrowserPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        # Keep navigation in-app to avoid unexpected external browser launches.
        if nav_type == QWebEnginePage.NavigationTypeLinkClicked and url.scheme() in {"http", "https"}:
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

    def createWindow(self, _window_type):
        # Block popup windows from auto-opening external browser windows.
        return None


class JarvisWebBridge(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.assistant_name = _assistant_name()
        self.weather_city = _weather_city()
        self.assistant = SafeControlAssistant()
        self.automation = None
        try:
            self.automation = EnhancedProfessionalAIAutomation()
        except Exception as exc:
            logging.warning("Automation bridge unavailable: %s", exc)
        self.speech_recognizer = None
        self.conversation = None
        self.authenticator = None
        self._auth_init_error = ""
        self.authenticated = False
        self._auth_setup_inflight = False
        self._auth_setup_message = ""
        self._auth_setup_error = ""
        self._auth_lock = threading.Lock()
        self._auth_setup_thread = None
        self._auth_unlock_thread = None
        self.mic_enabled = False
        self._stt_lock = threading.Lock()
        self._stt_inflight = False
        self._stt_cached_transcript = ""
        self._stt_cached_error = ""
        net = psutil.net_io_counters()
        self._last_net_sent = float(getattr(net, "bytes_sent", 0.0))
        self._last_net_recv = float(getattr(net, "bytes_recv", 0.0))
        self._last_net_ts = time.time()
        self._notification_manager = None
        self._job_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="jarvis-ui")
        self._jobs = {}
        self._jobs_lock = threading.Lock()

    def _submit_job(self, fn, *args, **kwargs) -> str:
        job_id = str(uuid.uuid4())
        future = self._job_executor.submit(fn, *args, **kwargs)
        with self._jobs_lock:
            self._jobs[job_id] = future
        return job_id

    def _get_job(self, job_id: str):
        with self._jobs_lock:
            return self._jobs.get(job_id)

    def _maybe_automation_first(self, command: str) -> str:
        if self.automation is None:
            return ""
        low = (command or "").strip().lower()
        prefixes = ("open ", "search ", "google ", "find ", "system ", "list apps", "bluetooth ", "turn on ", "turn off ", "volume ", "mute", "press ", "type ", "take ")
        if not low.startswith(prefixes):
            return ""
        return str(self.automation.process_command(command))

    def _get_notif_manager(self):
        if self._notification_manager is not None:
            return self._notification_manager
        try:
            from gui.notifications import NotificationManager

            self._notification_manager = NotificationManager()
            return self._notification_manager
        except Exception as exc:
            logging.warning("Could not initialize NotificationManager: %s", exc)
            self._notification_manager = None
            return None

    def _normalize_orbit_source(self, raw_source: str) -> str:
        key = str(raw_source or "system").strip().lower()
        aliases = {
            "mail": "gmail",
            "email": "gmail",
            "googlemail": "gmail",
            "wa": "whatsapp",
            "insta": "instagram",
            "ig": "instagram",
            "fb": "facebook",
            "msg": "messenger",
            "x": "twitter",
            "twit": "twitter",
            "calendar": "outlook",
            "teams": "outlook",
        }
        return aliases.get(key, key)

    def _notification_severity(self, notif: dict) -> str:
        if not isinstance(notif, dict):
            return "info"
        if bool(notif.get("urgent")):
            return "critical"
        raw = str(notif.get("severity") or notif.get("priority") or notif.get("level") or "").strip().lower()
        if raw in {"critical", "error", "alert", "fatal", "high"}:
            return "critical"
        if raw in {"important", "warning", "warn", "medium"}:
            return "important"
        if raw in {"success", "done", "completed", "ok"}:
            return "success"
        text = " ".join(
            [
                str(notif.get("title") or ""),
                str(notif.get("message") or ""),
                str(notif.get("body") or ""),
                str(notif.get("tag") or ""),
            ]
        ).lower()
        if any(k in text for k in ["failed", "denied", "security", "error", "critical"]):
            return "critical"
        if any(k in text for k in ["reminder", "pending", "warning", "soon"]):
            return "important"
        if any(k in text for k in ["sent", "completed", "success", "done"]):
            return "success"
        return "info"

    def _get_authenticator(self):
        if self.authenticator is not None:
            return self.authenticator
        if self._auth_init_error:
            return None
        try:
            from core.auth import EnhancedAdminOnlyAuth

            self.authenticator = EnhancedAdminOnlyAuth()
            return self.authenticator
        except Exception as exc:
            self._auth_init_error = f"Authentication backend unavailable: {exc}"
            return None

    def _ensure_conversation(self):
        if self.conversation is not None and self.speech_recognizer is not None:
            return True, ""
        try:
            self.speech_recognizer = WorkingSpeechRecognition(language="en-US")
            self.conversation = ConversationManager(self.assistant, self.speech_recognizer)
            return True, ""
        except Exception as exc:
            self.speech_recognizer = None
            self.conversation = None
            return False, f"Voice subsystem unavailable: {exc}"

    def _set_auth_state(self, *, authenticated=None, inflight=None, message=None, error=None):
        with self._auth_lock:
            if authenticated is not None:
                self.authenticated = bool(authenticated)
            if inflight is not None:
                self._auth_setup_inflight = bool(inflight)
            if message is not None:
                self._auth_setup_message = str(message)
            if error is not None:
                self._auth_setup_error = str(error)

    def _get_auth_state(self):
        with self._auth_lock:
            return {
                "authenticated": bool(self.authenticated),
                "inflight": bool(self._auth_setup_inflight),
                "message": str(self._auth_setup_message or ""),
                "error": str(self._auth_setup_error or ""),
            }

    def _first_setup_allowed(self) -> bool:
        auth = self._get_authenticator()
        if auth is None:
            return False
        has_face = bool(getattr(auth, "has_face_setup", lambda: False)())
        if auth.setup_completed:
            return False
        return not has_face

    def _auth_payload(self, message: str = ""):
        setup_required = self._first_setup_allowed()
        auth = self._get_authenticator()
        state = self._get_auth_state()
        has_face = bool(getattr(auth, "has_face_setup", lambda: False)()) if auth else False
        if state["inflight"]:
            effective_message = state["message"] or "Face enrollment in progress..."
        else:
            effective_message = message or state["message"] or (
                "Authentication required" if not state["authenticated"] else "Unlocked"
            )
        if auth is None and self._auth_init_error:
            effective_message = self._auth_init_error
        return {
            "ok": True,
            "authenticated": state["authenticated"],
            "locked": not state["authenticated"],
            "setup_required": setup_required,
            "has_face": has_face,
            "has_pin": False,
            "in_progress": state["inflight"],
            "message": effective_message,
        }

    def _auth_required_response(self, message: str = "Authentication required"):
        payload = self._auth_payload(message)
        payload["ok"] = False
        return json.dumps(payload)

    def _is_authenticated(self):
        return self._get_auth_state()["authenticated"]

    @pyqtSlot(result=str)
    def authStatus(self):
        return json.dumps(self._auth_payload())

    @pyqtSlot(str, result=str)
    def authSetupFacePinStatus(self, pin_code: str):
        _ = pin_code
        return self.authSetupFaceStatus()

    @pyqtSlot(result=str)
    @GracefulErrorHandler.handle_bridge_error
    def authSetupFaceStatus(self):
        try:
            auth = self._get_authenticator()
            if auth is None:
                return json.dumps({"ok": False, "message": self._auth_init_error or "Authentication backend unavailable"})
            if self._get_auth_state()["inflight"]:
                return json.dumps(self._auth_payload("Face setup is already in progress..."))
            if not self._first_setup_allowed():
                return json.dumps({"ok": False, "message": "First-time setup is disabled after provisioning"})

            self._set_auth_state(inflight=True, error="", message="Face enrollment started. Please look at the camera...")

            def _setup_worker():
                try:
                    if not auth.capture_admin_face():
                        reason = (getattr(auth, "last_error", "") or "Face enrollment failed").strip()
                        self._set_auth_state(authenticated=False, error=reason, message=reason)
                        return

                    auth.setup_completed = True
                    self._set_auth_state(authenticated=True, error="", message="Face setup completed. System unlocked.")
                except Exception as exc:
                    err = f"Auth setup error: {exc}"
                    self._set_auth_state(authenticated=False, error=err, message=err)
                finally:
                    self._set_auth_state(inflight=False)

            self._auth_setup_thread = threading.Thread(target=_setup_worker, daemon=True)
            self._auth_setup_thread.start()
            return json.dumps(self._auth_payload("Face enrollment started. Please look at the camera..."))
        except Exception as exc:
            self._set_auth_state(authenticated=False, inflight=False)
            return json.dumps({"ok": False, "message": f"Auth setup error: {exc}"})

    @pyqtSlot(str, str, result=str)
    def authPinChangeStatus(self, current_pin: str, new_pin: str):
        _ = current_pin
        _ = new_pin
        return json.dumps({"ok": False, "message": "PIN authentication has been removed"})

    @pyqtSlot(str, result=str)
    def authFaceAddStatus(self, _legacy_pin_code: str):
        return self.authFaceAddNoPinStatus()

    @pyqtSlot(result=str)
    @GracefulErrorHandler.handle_bridge_error
    def authFaceAddNoPinStatus(self):
        try:
            auth = self._get_authenticator()
            if auth is None:
                return json.dumps({"ok": False, "message": self._auth_init_error or "Authentication backend unavailable"})
            if not self._is_authenticated():
                return self._auth_required_response("Unlock system first")
            if self._get_auth_state()["inflight"]:
                return json.dumps(self._auth_payload("Face enrollment is already in progress..."))

            self._set_auth_state(inflight=True, error="", message="Face enrollment started. Please look at the camera...")

            def _face_add_worker():
                try:
                    if not auth.capture_admin_face():
                        reason = (getattr(auth, "last_error", "") or "Face enrollment failed").strip()
                        self._set_auth_state(error=reason, message=reason)
                        return
                    self._set_auth_state(error="", message="Face data updated successfully")
                except Exception as exc:
                    err = f"Face update error: {exc}"
                    self._set_auth_state(error=err, message=err)
                finally:
                    self._set_auth_state(inflight=False)

            self._auth_setup_thread = threading.Thread(target=_face_add_worker, daemon=True)
            self._auth_setup_thread.start()
            return json.dumps(self._auth_payload("Face enrollment started. Please look at the camera..."))
        except Exception as exc:
            self._set_auth_state(inflight=False)
            return json.dumps({"ok": False, "message": f"Face update error: {exc}"})

    @pyqtSlot(str, result=str)
    def authFaceRemoveStatus(self, _legacy_pin_code: str):
        return self.authFaceRemoveNoPinStatus()

    @pyqtSlot(result=str)
    @GracefulErrorHandler.handle_bridge_error
    def authFaceRemoveNoPinStatus(self):
        try:
            auth = self._get_authenticator()
            if auth is None:
                return json.dumps({"ok": False, "message": self._auth_init_error or "Authentication backend unavailable"})
            if not self._is_authenticated():
                return self._auth_required_response("Unlock system first")
            if not auth.remove_admin_face():
                reason = (getattr(auth, "last_error", "") or "Face removal failed").strip()
                return json.dumps({"ok": False, "message": reason})
            return json.dumps(self._auth_payload("Face data removed"))
        except Exception as exc:
            return json.dumps({"ok": False, "message": f"Face remove error: {exc}"})

    @pyqtSlot(result=str)
    def authCameraUnlockStatus(self):
        try:
            auth = self._get_authenticator()
            if auth is None:
                return json.dumps({"ok": False, "message": self._auth_init_error or "Authentication backend unavailable"})
            if not auth.setup_completed:
                return json.dumps({"ok": False, "message": "Setup required first"})

            if self._get_auth_state()["inflight"]:
                return json.dumps(self._auth_payload("Authentication already in progress..."))

            self._set_auth_state(inflight=True, error="", message="Face authentication started. Please look at the camera...")

            def _unlock_worker():
                try:
                    verified = False
                    last_reason = ""

                    # Camera quality can fluctuate between reads; retry briefly before failing.
                    for attempt in range(2):
                        verified = bool(auth.verify_admin_face())
                        if verified:
                            break
                        last_reason = (getattr(auth, "last_error", "") or "").strip()
                        if attempt == 0:
                            time.sleep(0.5)

                    # Fallback path: if full verification misses, try a quick single-frame check.
                    if not verified and hasattr(auth, "quick_face_check"):
                        try:
                            verified = bool(auth.quick_face_check())
                        except Exception:
                            verified = False

                    if verified:
                        self._set_auth_state(authenticated=True, message="Face authentication successful", error="")
                    else:
                        backend = str(getattr(auth, "face_backend", "legacy") or "legacy")
                        reason = (getattr(auth, "last_error", "") or last_reason or f"Face authentication failed ({backend})").strip()
                        self._set_auth_state(authenticated=False, error=reason, message=reason)
                except Exception as exc:
                    err = f"Face auth error: {exc}"
                    self._set_auth_state(authenticated=False, error=err, message=err)
                finally:
                    self._set_auth_state(inflight=False)

            self._auth_unlock_thread = threading.Thread(target=_unlock_worker, daemon=True)
            self._auth_unlock_thread.start()
            return json.dumps(self._auth_payload("Face authentication started. Please look at the camera..."))
        except Exception as exc:
            self._set_auth_state(authenticated=False)
            return json.dumps({"ok": False, "message": f"Face auth error: {exc}"})

    @pyqtSlot(str, result=str)
    def authPinUnlockStatus(self, pin_code: str):
        _ = pin_code
        self._set_auth_state(authenticated=False)
        return json.dumps({"ok": False, "message": "PIN authentication has been removed"})

    @pyqtSlot(result=str)
    def authLockStatus(self):
        self._set_auth_state(authenticated=False)
        self.mic_enabled = False
        try:
            if self.conversation is not None:
                self.conversation.stop()
        except Exception:
            pass
        return json.dumps(self._auth_payload("System locked"))

    @pyqtSlot(str)
    def runCommand(self, command: str):
        if not self._is_authenticated():
            return
        self._run_command(command)

    @pyqtSlot(str, result=str)
    def runCommandStatus(self, command: str):
        if not self._is_authenticated():
            return self._auth_required_response()
        return self._run_command_status(command)

    @pyqtSlot(str, result=str)
    def askAssistant(self, text: str):
        if not self._is_authenticated():
            return self._auth_required_response()
        query = (text or "").strip()
        if not query:
            return json.dumps({"ok": False, "message": "Empty message", "response": ""})
        try:
            auto = self._maybe_automation_first(query)
            if auto and "unknown command" not in auto.lower():
                return json.dumps({"ok": True, "message": "Automation reply generated", "response": auto})
            response = self.assistant.process(query)
            return json.dumps({"ok": True, "message": "Reply generated", "response": str(response or "")})
        except Exception as exc:
            return json.dumps({"ok": False, "message": f"Assistant failed: {exc}", "response": ""})

    @pyqtSlot(str, result=str)
    def runAutomationAsync(self, command: str):
        if not self._is_authenticated():
            return self._auth_required_response()
        if self.automation is None:
            return json.dumps({"ok": False, "message": "Automation bridge unavailable"})

        clean = (command or "").strip()
        if not clean:
            return json.dumps({"ok": False, "message": "Empty command"})

        job_id = self._submit_job(self.automation.process_command, clean)
        return json.dumps({"ok": True, "job_id": job_id, "message": "Automation command queued"})

    @pyqtSlot(str, result=str)
    def parseAutomationStatus(self, command: str):
        if not self._is_authenticated():
            return self._auth_required_response()
        if self.automation is None:
            return json.dumps({"ok": False, "message": "Automation bridge unavailable"})

        clean = (command or "").strip()
        if not clean:
            return json.dumps({"ok": False, "message": "Empty command"})

        try:
            parsed = self.automation.parse_natural_command(clean)
            commands = self._commands_from_parsed(parsed)
            visual = [self._visualize_command(cmd) for cmd in commands]
            return json.dumps(
                {
                    "ok": True,
                    "message": "Command parsed",
                    "input": clean,
                    "parsed": parsed,
                    "commands": commands,
                    "visual": visual,
                }
            )
        except Exception as exc:
            return json.dumps({"ok": False, "message": f"Parse failed: {exc}"})

    @pyqtSlot(str, result=str)
    def executeParsedAutomationStatus(self, parsed_payload: str):
        if not self._is_authenticated():
            return self._auth_required_response()
        if self.automation is None:
            return json.dumps({"ok": False, "message": "Automation bridge unavailable"})

        raw = (parsed_payload or "").strip()
        if not raw:
            return json.dumps({"ok": False, "message": "Empty parsed payload"})

        try:
            parsed = json.loads(raw)
        except Exception as exc:
            return json.dumps({"ok": False, "message": f"Invalid parsed payload: {exc}"})

        commands = self._commands_from_parsed(parsed)
        if not commands:
            return json.dumps({"ok": False, "message": "No parsed commands to execute", "results": []})

        results = []
        had_error = False
        for cmd in commands:
            action = str(cmd.get("action") or "unknown")
            params = {k: v for k, v in cmd.items() if k != "action"}

            if action == "unknown":
                unknown_text = str(params.get("command") or "")
                suggestions = self.automation._suggest_actions(unknown_text)
                if suggestions:
                    suggested_lines = "\n".join([f" - {item}" for item in suggestions])
                    result_text = (
                        f" Unknown command: '{unknown_text}'\n"
                        " Did you mean:\n"
                        f"{suggested_lines}"
                    )
                else:
                    result_text = (
                        f" Unknown command: '{unknown_text}'\n"
                        " Try: 'open browser', 'system info', 'list apps', or 'help'"
                    )
                had_error = True
            else:
                result_text = str(self.automation.execute_command(action, **params))
                if "failed" in result_text.lower() or " unknown command" in result_text.lower():
                    had_error = True

            results.append({"action": action, "result": result_text})

        return json.dumps(
            {
                "ok": True,
                "status": "error" if had_error else "success",
                "message": "Execution completed",
                "results": results,
                "result_text": "\n".join([str(item.get("result", "")) for item in results]).strip(),
            }
        )

    @pyqtSlot(str, result=str)
    def getAsyncResult(self, job_id: str):
        if not self._is_authenticated():
            return self._auth_required_response()
        future = self._get_job(job_id)
        if future is None:
            return json.dumps({"ok": False, "message": "Unknown job id", "done": True})

        if not future.done():
            return json.dumps({"ok": True, "done": False, "status": "running"})

        try:
            result = str(future.result())
            return json.dumps({"ok": True, "done": True, "status": "completed", "result": result})
        except Exception as exc:
            return json.dumps({"ok": False, "done": True, "status": "failed", "message": str(exc)})

    @pyqtSlot(str, result=str)
    def generateImage(self, prompt: str):
        if not self._is_authenticated():
            return self._auth_required_response()
        clean = (prompt or "").strip()
        if not clean:
            return json.dumps({"ok": False, "message": "Empty image prompt", "images": []})
        try:
            result = generate_images_with_progress(clean, count=4, style="realistic")
            if not isinstance(result, dict):
                return json.dumps({"ok": False, "message": "Image generation returned invalid payload", "images": []})
            return json.dumps(result)
        except Exception as exc:
            return json.dumps({"ok": False, "message": f"Image generation failed: {exc}", "images": []})

    @pyqtSlot(str, result=str)
    def searchWithProgress(self, query: str):
        if not self._is_authenticated():
            return self._auth_required_response()
        clean = (query or "").strip()
        if not clean:
            return json.dumps({"ok": False, "message": "Empty search query", "progress": 0, "results": []})
        try:
            result = search_with_progress(clean, search_type="web")
            if not isinstance(result, dict):
                return json.dumps({"ok": False, "message": "Search returned invalid payload", "progress": 0, "results": []})
            return json.dumps(result)
        except Exception as exc:
            return json.dumps({"ok": False, "message": f"Search failed: {exc}", "progress": 0, "results": []})

    @pyqtSlot(str, result=str)
    def classifyQuery(self, query: str):
        if not self._is_authenticated():
            return self._auth_required_response()
        clean = (query or "").strip()
        if not clean:
            return json.dumps({"ok": False, "message": "Empty classify query"})
        try:
            result = classify_with_confidence(clean)
            result["ok"] = True
            return json.dumps(result)
        except Exception as exc:
            return json.dumps({"ok": False, "message": f"Classification failed: {exc}"})

    @pyqtSlot(result=str)
    def micOnStatus(self):
        if not self._is_authenticated():
            return self._auth_required_response()
        ok, message = self._ensure_conversation()
        if not ok:
            return json.dumps({"ok": False, "message": message})
        self.mic_enabled = True
        if self.conversation is not None:
            self.conversation.start()
        wake = self.conversation.wake_word if getattr(self.conversation, "wake_enabled", False) else ""
        if wake:
            return json.dumps({"ok": True, "message": f"Microphone enabled. Say '{wake}' to start."})
        return json.dumps({"ok": True, "message": "Microphone enabled"})

    @pyqtSlot(result=str)
    def micOffStatus(self):
        if not self._is_authenticated():
            return self._auth_required_response()
        self.mic_enabled = False
        if self.conversation is not None:
            self.conversation.stop()
        with self._stt_lock:
            self._stt_cached_transcript = ""
            self._stt_cached_error = ""
        return json.dumps({"ok": True, "message": "Microphone muted"})

    @pyqtSlot(result=str)
    def conversationStatus(self):
        if not self._is_authenticated():
            return self._auth_required_response()
        ok, message = self._ensure_conversation()
        if not ok:
            return json.dumps({"ok": False, "message": message, "running": False})
        data = self.conversation.status()
        return json.dumps(data)

    @pyqtSlot(str, result=str)
    def conversationSubmitStatus(self, text: str):
        if not self._is_authenticated():
            return self._auth_required_response()
        ok, message = self._ensure_conversation()
        if not ok:
            return json.dumps({"ok": False, "message": message})
        clean = (text or "").strip()
        if not clean:
            return json.dumps({"ok": False, "message": "Empty message"})
        accepted = self.conversation.submit_text(clean)
        if not accepted:
            return json.dumps({"ok": False, "message": "Conversation submit failed"})
        return json.dumps({"ok": True, "message": "Conversation text submitted"})

    @pyqtSlot(bool, result=str)
    def conversationSetVoiceMutedStatus(self, muted: bool):
        if not self._is_authenticated():
            return self._auth_required_response()
        ok, message = self._ensure_conversation()
        if not ok:
            return json.dumps({"ok": False, "message": message, "voice_muted": bool(muted)})
        self.conversation.set_output_muted(bool(muted))
        state = "muted" if muted else "unmuted"
        return json.dumps({"ok": True, "message": f"Voice output {state}", "voice_muted": bool(muted)})

    @pyqtSlot(result=str)
    def conversationInterruptStatus(self):
        if not self._is_authenticated():
            return self._auth_required_response()
        if self.conversation is not None:
            self.conversation.interrupt()
        return json.dumps({"ok": True, "message": "Conversation interrupted"})

    def _capture_stt_once(self):
        transcript = ""
        error_message = ""

        try:
            if self.speech_recognizer is None:
                ok, message = self._ensure_conversation()
                if not ok:
                    raise RuntimeError(message)
            heard = self.speech_recognizer.listen_once(timeout=4, phrase_time_limit=8)
            transcript = str(heard or "").strip()
        except Exception as exc:
            error_message = f"STT failed: {exc}"

        with self._stt_lock:
            if transcript:
                self._stt_cached_transcript = transcript
                self._stt_cached_error = ""
            elif error_message:
                self._stt_cached_error = error_message
            self._stt_inflight = False

    @pyqtSlot(result=str)
    def sttStatus(self):
        if not self._is_authenticated():
            return self._auth_required_response()
        if self.mic_enabled:
            if self.conversation is not None:
                status = self.conversation.status()
                final_text = (status.get("final_transcript") or "").strip()
                interim_text = (status.get("interim_transcript") or "").strip()
                if final_text:
                    return json.dumps({"ok": True, "message": "Speech captured", "transcript": final_text})
                if interim_text:
                    return json.dumps({"ok": True, "message": "Listening", "transcript": ""})
            else:
                ok, message = self._ensure_conversation()
                if not ok:
                    return json.dumps({"ok": False, "message": message, "transcript": ""})

        if not self.mic_enabled:
            return json.dumps({"ok": False, "message": "Microphone is muted", "transcript": ""})

        with self._stt_lock:
            if self._stt_cached_error:
                message = self._stt_cached_error
                self._stt_cached_error = ""
                return json.dumps({"ok": False, "message": message, "transcript": ""})

            if self._stt_cached_transcript:
                transcript = self._stt_cached_transcript
                self._stt_cached_transcript = ""
                return json.dumps({"ok": True, "message": "Speech captured", "transcript": transcript})

            if self._stt_inflight:
                return json.dumps({"ok": True, "message": "Listening", "transcript": ""})

            self._stt_inflight = True

        worker = threading.Thread(target=self._capture_stt_once, daemon=True)
        worker.start()
        return json.dumps({"ok": True, "message": "Listening", "transcript": ""})

    @pyqtSlot(str, result=str)
    def speakStatus(self, text: str):
        if not self._is_authenticated():
            return self._auth_required_response()
        message = (text or "").strip()
        if not message:
            return json.dumps({"ok": False, "message": "Empty speech text"})

        try:
            tts_result = tts_speak(message)
            normalized = str(tts_result).strip().lower()
            ok = not normalized.startswith(("error", "failed"))
            return json.dumps({"ok": ok, "message": str(tts_result)})
        except Exception as exc:
            return json.dumps({"ok": False, "message": f"TTS failed: {exc}"})

    @pyqtSlot()
    def shutdownApp(self):
        app = QApplication.instance()
        if app is None:
            return
        try:
            window = app.activeWindow()
            if window:
                window.close()
                return
        except Exception:
            pass
        app.quit()

    @pyqtSlot(result=str)
    def shutdownStatus(self):
        if not self._is_authenticated():
            return self._auth_required_response()
        QTimer.singleShot(120, self.shutdownApp)
        return json.dumps({"ok": True, "message": "Shutdown requested"})

    @pyqtSlot()
    def restartApp(self):
        script_path = os.path.abspath(sys.argv[0])
        args = [sys.executable, script_path, *sys.argv[1:]]
        try:
            subprocess.Popen(args, cwd=os.getcwd())
            self.shutdownApp()
        except Exception:
            return

    @pyqtSlot(result=str)
    def restartStatus(self):
        if not self._is_authenticated():
            return self._auth_required_response()
        QTimer.singleShot(120, self.restartApp)
        return json.dumps({"ok": True, "message": "Restart requested"})

    @pyqtSlot()
    def mediaPlayPause(self):
        self._run_media_command(["playerctl", "play-pause"])

    @pyqtSlot()
    def mediaNext(self):
        self._run_media_command(["playerctl", "next"])

    @pyqtSlot()
    def mediaPrevious(self):
        self._run_media_command(["playerctl", "previous"])

    @pyqtSlot(str, result=str)
    def mediaStatus(self, action: str):
        if not self._is_authenticated():
            return self._auth_required_response()
        mapping = {
            "playpause": ["playerctl", "play-pause"],
            "next": ["playerctl", "next"],
            "previous": ["playerctl", "previous"],
        }
        key = (action or "").strip().lower()
        cmd = mapping.get(key)
        if not cmd:
            return json.dumps({"ok": False, "message": f"Unknown media action: {action}"})
        ok, message = self._run_media_command(cmd)
        return json.dumps({"ok": ok, "message": message})

    @pyqtSlot(result=str)
    def getSystemStats(self):
        now = datetime.now()
        snapshot = get_system_stats_snapshot()
        down_mbps, up_mbps = self._net_rates_mbps()

        payload = {
            "time": now.strftime("%H:%M"),
            "day": now.strftime("%d"),
            "month": now.strftime("%b").upper(),
            "ram_percent": int(round(float(snapshot.get("memory_percent", 0.0)))),
            "wifi_label": "Online",
            "down_mbps": round(down_mbps, 2),
            "up_mbps": round(up_mbps, 2),
            "online": bool(self.authenticated),
            "auth_locked": not bool(self.authenticated),
        }
        return json.dumps(payload)

    @pyqtSlot(result=str)
    def getNotifications(self) -> str:
        try:
            mgr = self._get_notif_manager()
            if mgr is None:
                return json.dumps([])

            raw_notifs = mgr.get_notifications()
            result = []
            for notif in raw_notifs:
                source = self._normalize_orbit_source(
                    notif.get("source")
                    or notif.get("app")
                    or notif.get("tag")
                    or notif.get("notification_type")
                    or "system"
                )
                title = str(notif.get("title") or notif.get("message") or "")
                body = str(notif.get("body") or notif.get("message") or "")
                result.append(
                    {
                        "source": source,
                        "tag": str(notif.get("tag") or source.upper()),
                        "title": title,
                        "body": body,
                        "severity": self._notification_severity(notif),
                        "timestamp": str(notif.get("timestamp") or notif.get("time") or ""),
                        "read": bool(notif.get("read", False)),
                    }
                )
            return json.dumps(result)
        except Exception:
            logging.exception("getNotifications failed")
            return json.dumps([])

    @pyqtSlot(result=str)
    def notificationCount(self) -> str:
        try:
            mgr = self._get_notif_manager()
            if mgr is None:
                return "0"
            notifs = mgr.get_notifications()
            unread = sum(1 for n in notifs if not n.get("read", False))
            return str(unread)
        except Exception:
            return "0"

    @pyqtSlot(str, result=str)
    def markNotificationRead(self, source: str) -> str:
        try:
            mgr = self._get_notif_manager()
            if mgr is None:
                return json.dumps({"ok": False, "message": "NotificationManager unavailable"})

            normalized_source = self._normalize_orbit_source(source)
            if hasattr(mgr, "mark_read_by_source"):
                updated = mgr.mark_read_by_source(normalized_source)
            else:
                updated = 0
                for notif in getattr(mgr, "notifications", []):
                    current = self._normalize_orbit_source(
                        notif.get("source")
                        or notif.get("app")
                        or notif.get("tag")
                        or notif.get("notification_type")
                        or "system"
                    )
                    if current == normalized_source and not notif.get("read", False):
                        notif["read"] = True
                        updated += 1
                if updated and hasattr(mgr, "save_notifications"):
                    mgr.save_notifications()

            return json.dumps({"ok": True, "updated": int(updated), "source": normalized_source})
        except Exception as exc:
            logging.exception("markNotificationRead failed")
            return json.dumps({"ok": False, "message": str(exc)})

    @pyqtSlot(result=str)
    def mapConfigStatus(self):
        env = dotenv_values(".env")
        api_key = (
            os.getenv("MAPTILER_API_KEY")
            or os.getenv("MAP_API_KEY")
            or env.get("MAPTILER_API_KEY")
            or env.get("MAP_API_KEY")
            or ""
        )

        if not api_key:
            return json.dumps({
                "ok": True,
                "message": "Using demo WebGL map configuration",
                "provider": "demo",
                "road_style": "https://demotiles.maplibre.org/style.json",
                "satellite_style": "",
                "terrain_tiles": "",
            })

        return json.dumps({
            "ok": True,
            "message": "Map config ready",
            "provider": "maptiler",
            "road_style": f"https://api.maptiler.com/maps/streets-v2/style.json?key={api_key}",
            "satellite_style": f"https://api.maptiler.com/maps/hybrid/style.json?key={api_key}",
            "terrain_tiles": f"https://api.maptiler.com/tiles/terrain-rgb-v2/tiles.json?key={api_key}",
        })

    def _net_rates_mbps(self):
        try:
            now_ts = time.time()
            net = psutil.net_io_counters()
            sent_now = float(getattr(net, "bytes_sent", 0.0))
            recv_now = float(getattr(net, "bytes_recv", 0.0))

            elapsed = max(0.001, now_ts - self._last_net_ts)
            down_bps = max(0.0, (recv_now - self._last_net_recv) / elapsed)
            up_bps = max(0.0, (sent_now - self._last_net_sent) / elapsed)

            self._last_net_sent = sent_now
            self._last_net_recv = recv_now
            self._last_net_ts = now_ts

            down_mbps = (down_bps * 8.0) / 1_000_000.0
            up_mbps = (up_bps * 8.0) / 1_000_000.0
            return down_mbps, up_mbps
        except Exception:
            return 0.0, 0.0

    def _run_media_command(self, command):
        if shutil.which(command[0]) is None:
            return False, f"{command[0]} not found"
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, "Media command sent"
        except Exception as exc:
            return False, f"Media command failed: {exc}"

    def _launch_command(self, cmd):
        if not cmd:
            return False
        exe = cmd[0]
        if os.path.isabs(exe):
            if not os.path.exists(exe):
                return False
        elif shutil.which(exe) is None:
            return False
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def _launch_url_command(self, args):
        if not args:
            return False
        if shutil.which(args[0]) is None:
            return False
        try:
            completed = subprocess.run(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
                check=False,
            )
            return completed.returncode == 0
        except Exception:
            return False

    def _open_url(self, url: str):
        for opener in (["xdg-open", url], ["gio", "open", url], ["sensible-browser", url]):
            if self._launch_url_command(opener):
                return True
        try:
            return bool(webbrowser.open(url))
        except Exception:
            return False

    def _commands_from_parsed(self, parsed):
        if isinstance(parsed, dict) and parsed.get("action") == "multi":
            commands = parsed.get("commands")
            if isinstance(commands, list):
                return [cmd for cmd in commands if isinstance(cmd, dict)]
            return []
        if isinstance(parsed, dict):
            return [parsed]
        if isinstance(parsed, list):
            return [cmd for cmd in parsed if isinstance(cmd, dict)]
        return []

    def _visualize_command(self, cmd: dict) -> dict:
        action = str(cmd.get("action") or "unknown")
        label = action.replace("_", " ").title()
        target = str(
            cmd.get("app_name")
            or cmd.get("website")
            or cmd.get("query")
            or cmd.get("url")
            or cmd.get("text")
            or cmd.get("keys")
            or cmd.get("command")
            or ""
        )
        return {"action": action, "label": label, "target": target}

    def _run_command(self, command: str):
        self._run_command_status(command)

    def _run_command_status(self, command: str):
        low = (command or "").strip().lower()
        if not low:
            return json.dumps({"ok": False, "message": "Empty command"})

        auto = self._maybe_automation_first(command)
        if auto and "unknown command" not in auto.lower():
            return json.dumps({"ok": True, "message": auto})

        if low == "open discord":
            if self._open_url("discord://-/channels/@me"):
                return json.dumps({"ok": True, "message": "Opened Discord"})
            if self._open_url("https://discord.com/app"):
                return json.dumps({"ok": True, "message": "Opened Discord in browser"})
            return json.dumps({"ok": False, "message": "Failed to open Discord"})

        folder_map = {
            "open downloads": os.path.expanduser("~/Downloads"),
            "open documents": os.path.expanduser("~/Documents"),
            "open pictures": os.path.expanduser("~/Pictures"),
            "open music": os.path.expanduser("~/Music"),
            "open videos": os.path.expanduser("~/Videos"),
        }

        if low in {"shutdown", "app shutdown", "close app"}:
            return self.shutdownStatus()

        if low in {"restart", "restart app", "app restart"}:
            return self.restartStatus()

        if low in folder_map:
            target = folder_map[low]
            if not os.path.exists(target):
                return json.dumps({"ok": False, "message": f"Folder not found: {target}"})
            if shutil.which("xdg-open") is None:
                return json.dumps({"ok": False, "message": "xdg-open not found"})
            try:
                subprocess.Popen(["xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return json.dumps({"ok": True, "message": f"Opened {Path(target).name}"})
            except Exception as exc:
                return json.dumps({"ok": False, "message": f"Failed opening folder: {exc}"})

        app_map = {
            "open terminal": [["x-terminal-emulator"], ["gnome-terminal"], ["konsole"], ["xfce4-terminal"], ["xterm"]],
            "open vscode": [["code"]],
            "open libreoffice": [["libreoffice"]],
            "open gimp": [["gimp"]],
            "open steam": [["steam"], ["flatpak", "run", "com.valvesoftware.Steam"]],
            "open spotify": [["spotify"], ["flatpak", "run", "com.spotify.Client"], ["snap", "run", "spotify"]],
            "open epic games": [["heroic"], ["legendary"], ["flatpak", "run", "com.heroicgameslauncher.hgl"], ["lutris"], ["lutris", "lutris:rungameid/epic-games-store"], ["gtk-launch", "heroic.desktop"], ["gtk-launch", "com.heroicgameslauncher.hgl.desktop"]],
        }

        web_map = {
            "open youtube": "https://www.youtube.com",
            "open google": "https://www.google.com",
            "open firefox web": "https://www.google.com",
            "open chrome": "https://www.google.com",
            "open gmail": "https://mail.google.com",
            "open whatsapp": "https://web.whatsapp.com",
            "open discord": "https://discord.com/app",
            "open spotify": "https://open.spotify.com",
            "open epic games": "https://store.epicgames.com",
            "open openai": "https://chat.openai.com",
            "open deepseek": "https://chat.deepseek.com",
            "open grok": "https://grok.com",
            "open wikipedia": "https://wikipedia.org",
            "open google calendar": "https://calendar.google.com",
            "open reminders": "https://calendar.google.com",
            "open notes": "https://keep.google.com",
            "open google drive": "https://drive.google.com",
            "open twitter": "https://x.com",
            "open linkedin": "https://www.linkedin.com",
            "open facebook": "https://www.facebook.com",
            "open messenger": "https://www.messenger.com",
            "open instagram": "https://www.instagram.com",
            "open outlook": "https://outlook.live.com",
            "open mail": "https://mail.google.com",
            "open gps": f"https://www.google.com/maps/search/?api=1&query={quote_plus(self.weather_city)}",
        }

        app_requested = low in app_map
        if app_requested:
            for cmd in app_map[low]:
                if self._launch_command(cmd):
                    return json.dumps({"ok": True, "message": f"Launched {command}"})
                continue

            if low == "open discord" and self._open_url("discord://-/channels/@me"):
                return json.dumps({"ok": True, "message": "Opened Discord protocol"})

            if low == "open epic games" and self._open_url("com.epicgames.launcher://apps"):
                return json.dumps({"ok": True, "message": "Opened Epic protocol"})

        if low in web_map:
            if self._open_url(web_map[low]):
                if app_requested:
                    return json.dumps({"ok": True, "message": f"App unavailable, opened web for {command}"})
                return json.dumps({"ok": True, "message": f"Opened {command}"})
            return json.dumps({"ok": False, "message": f"Failed opening link for: {command}"})

        if app_requested:
            return json.dumps({"ok": False, "message": f"App not available for: {command}"})

        try:
            response = self.assistant.process(command)
            return json.dumps({"ok": True, "message": str(response or "Command sent to assistant")})
        except Exception as exc:
            return json.dumps({"ok": False, "message": f"Assistant command failed: {exc}"})

    @pyqtSlot(result=str)
    def automationMetrics(self):
        if not self._is_authenticated():
            return self._auth_required_response()
        if self.automation is None:
            return json.dumps({"ok": False, "message": "Automation bridge unavailable"})
        try:
            payload = self.automation.get_observability_snapshot()
            payload["ok"] = True
            payload["plugins_loaded"] = list(getattr(self.automation, "_loaded_plugins", []))
            return json.dumps(payload)
        except Exception as exc:
            return json.dumps({"ok": False, "message": f"Could not fetch automation metrics: {exc}"})


class WebJarvisWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.assistant_name = _assistant_name()
        self.setWindowTitle(f"{self.assistant_name} Web Interface")
        self.setMinimumSize(1280, 720)

        self.browser = QWebEngineView(self)
        self.external_page = ExternalBrowserPage(self.browser)
        self.browser.setPage(self.external_page)
        self._configure_web_view()
        self.bridge = JarvisWebBridge(self)
        self.channel = QWebChannel(self.browser.page())
        self.channel.registerObject("jarvisBridge", self.bridge)
        self.browser.page().setWebChannel(self.channel)
        self.browser.page().featurePermissionRequested.connect(self._handle_feature_permission)

        self.setCentralWidget(self.browser)
        self._load_web_ui()

    def _configure_web_view(self):
        settings = self.browser.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.ErrorPageEnabled, True)
        settings.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)
        self.browser.setZoomFactor(1.0)

        if os.getenv("JARVIS_WEB_DEBUG", "0") == "1":
            self.devtools_page = QWebEnginePage(self.browser.page().profile(), self.browser)
            self.browser.page().setDevToolsPage(self.devtools_page)

    def _load_interface_from_html(self, html_path: Path, base_dir: Path):
        _ = base_dir
        self.browser.load(QUrl.fromLocalFile(str(html_path.resolve())))

    def _handle_feature_permission(self, security_origin: QUrl, feature):
        allowed = {
            QWebEnginePage.MediaAudioCapture,
            QWebEnginePage.MediaVideoCapture,
            QWebEnginePage.MediaAudioVideoCapture,
            QWebEnginePage.Geolocation,
        }
        policy = (
            QWebEnginePage.PermissionGrantedByUser
            if feature in allowed
            else QWebEnginePage.PermissionDeniedByUser
        )
        self.browser.page().setFeaturePermission(security_origin, feature, policy)

    def _load_web_ui(self):
        web_root = Path(__file__).resolve().parent / "web"
        source_index = web_root / "index.html"
        dist_index = web_root / "dist" / "index.html"

        if source_index.exists():
            self._load_interface_from_html(source_index, web_root)
            return

        if dist_index.exists():
            html = dist_index.read_text(encoding="utf-8")
            html = html.replace('src="/assets/', 'src="./assets/')
            html = html.replace('href="/assets/', 'href="./assets/')
            self.browser.setHtml(html, QUrl.fromLocalFile(str(dist_index.parent.resolve()) + "/"))
            return

        raise FileNotFoundError("Web UI not found: expected gui/web/index.html or gui/web/dist/index.html")

    def closeEvent(self, event):
        try:
            if hasattr(self, "bridge") and getattr(self, "bridge", None):
                try:
                    self.bridge.authLockStatus()
                except Exception:
                    pass
                try:
                    self.bridge.conversation.stop()
                except Exception:
                    pass

            page = self.browser.page() if hasattr(self, "browser") else None
            if page:
                try:
                    page.featurePermissionRequested.disconnect(self._handle_feature_permission)
                except Exception:
                    pass
                try:
                    page.setWebChannel(None)
                except Exception:
                    pass
                try:
                    page.profile().clearHttpCache()
                except Exception:
                    pass
            if hasattr(self, "browser") and self.browser:
                try:
                    self.browser.stop()
                except Exception:
                    pass
                try:
                    self.browser.deleteLater()
                except Exception:
                    pass
        except Exception:
            pass
        super().closeEvent(event)


SimpleJarvisWindow = WebJarvisWindow


def main():
    app = QApplication(sys.argv)
    try:
        # Web UI is the single supported desktop interface.
        window = WebJarvisWindow()
        window.showMaximized()
        return app.exec_()
    except Exception:
        logging.exception("Failed to start web UI")
        return 1
