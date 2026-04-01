#!/usr/bin/env python3
"""Main entry point for safe console assistant mode."""

import os
import sys
import logging
import re
import subprocess
import faulthandler
import threading
import importlib
import time
from pathlib import Path
from logging.handlers import RotatingFileHandler

from core.safe_control import SafeControlAssistant
from core.api_healthcheck import run_api_healthcheck, render_health_report
from core.migration import migrate_legacy_data, render_migration_summary
from core.config import ConfigManager, load_config, validate_config, render_validation_warnings
from core.paths import ensure_dirs
from core.channel_manager import channel_manager


PROJECT_ROOT = Path(__file__).resolve().parent
os.environ.setdefault("JARVIS_FACE_BACKEND", "legacy")
ensure_dirs()


def start_channel_services() -> tuple[bool, str]:
    """Start channel manager and optional webhook server based on env toggles."""
    if not ConfigManager.get_bool("JARVIS_CHANNEL_MANAGER_ENABLED", default=False):
        return False, "Channel manager disabled"

    created = channel_manager.register_from_config()
    channel_manager.start()
    message = f"Channel manager started ({len(channel_manager.channels)} channels, {created} newly registered)"

    if ConfigManager.get_bool("JARVIS_CHANNEL_WEBHOOKS_ENABLED", default=False):
        api = ConfigManager.get("JARVIS_CHANNEL_WEBHOOKS_API", default="fastapi").strip().lower() or "fastapi"
        host = ConfigManager.get("JARVIS_CHANNEL_WEBHOOKS_HOST", default="0.0.0.0")
        port = ConfigManager.get_int("JARVIS_CHANNEL_WEBHOOKS_PORT", default=8088)

        def _run_webhook_server():
            try:
                if api == "fastapi":
                    from core.channel_webhooks import create_fastapi_app
                    uvicorn = importlib.import_module("uvicorn")

                    app = create_fastapi_app()
                    uvicorn.run(app, host=host, port=port, log_level="info")
                elif api == "flask":
                    from core.channel_webhooks import create_flask_app

                    app = create_flask_app()
                    app.run(host=host, port=port)
                else:
                    logging.error("Unsupported JARVIS_CHANNEL_WEBHOOKS_API=%s", api)
            except Exception as exc:
                logging.exception("Webhook server failed to start: %s", exc)

        thread = threading.Thread(target=_run_webhook_server, daemon=True)
        thread.start()
        message = f"{message}; webhook server starting on {host}:{port} via {api}"

    return True, message


def stop_channel_services() -> None:
    """Stop channel manager on shutdown."""
    try:
        if channel_manager.running:
            channel_manager.stop()
    except Exception:
        logging.exception("Failed to stop channel manager cleanly")


def load_profile():
    env = ConfigManager.env_map(str(PROJECT_ROOT / ".env"))
    username = ConfigManager.get("Username", "USERNAME", default="User", env_map=env)
    assistant_name = ConfigManager.get("Assistantname", "AssistantName", "ASSISTANT_NAME", default="Jarvis", env_map=env)
    return username, assistant_name


def setup_logging():
    logs_dir = PROJECT_ROOT / "Data" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "jarvis.log"
    fault_file = logs_dir / "fault.log"

    try:
        fault_stream = open(fault_file, "a", encoding="utf-8")
        faulthandler.enable(file=fault_stream, all_threads=True)
    except Exception:
        pass

    logging.basicConfig(
        level=getattr(logging, ConfigManager.get("JARVIS_LOG_LEVEL", default="WARNING").upper(), logging.WARNING),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def _pyqt_plugin_path() -> str:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    candidates = [
        Path(sys.prefix) / "lib" / version / "site-packages" / "PyQt5" / "Qt5" / "plugins",
        Path(sys.prefix) / "lib64" / version / "site-packages" / "PyQt5" / "Qt5" / "plugins",
        PROJECT_ROOT / ".venv" / "lib" / version / "site-packages" / "PyQt5" / "Qt5" / "plugins",
        PROJECT_ROOT / ".venv" / "lib64" / version / "site-packages" / "PyQt5" / "Qt5" / "plugins",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def _normalize_qt_env() -> None:
    plugin_path = _pyqt_plugin_path()
    if plugin_path:
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_path
        os.environ["QT_PLUGIN_PATH"] = plugin_path

    qt_plugin_path = os.environ.get("QT_PLUGIN_PATH", "")
    if "cv2/qt/plugins" in qt_plugin_path:
        os.environ["QT_PLUGIN_PATH"] = plugin_path or ""


def _qt_gui_preflight() -> bool:
    env = os.environ.copy()
    probe = (
        "from PyQt5.QtWidgets import QApplication; "
        "app = QApplication([]); "
        "print('QT_OK')"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", probe],
            env=env,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        return completed.returncode == 0 and "QT_OK" in completed.stdout
    except Exception:
        return False


def run_console():
    username, assistant_name = load_profile()
    assistant = SafeControlAssistant()
    debug_input = ConfigManager.get_bool("JARVIS_DEBUG_INPUT", default=False)

    print(f"Parser version: {assistant.PARSER_VERSION}")
    print("Type 'help' to see supported commands")

    ignored_tokens = {
        "superm",
        "super+m",
        "super m",
        "meta+m",
        "meta m",
        "win+m",
        "cmd+m",
    }

    def sanitize_input(raw: str) -> str:
        text = raw.replace("\r", "").replace("\n", "")
        text = re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", text)
        text = "".join(ch for ch in text if ch.isprintable())
        return text.strip()

    def is_key_chord_artifact(value: str) -> bool:
        low = value.lower().strip()
        if low in ignored_tokens:
            return True
        return bool(re.fullmatch(r"(?:super|meta|cmd|win)[+ _-]?[a-z0-9]{1,6}", low))

    while True:
        try:
            raw_command = input(f"{username}@{assistant_name}> ")
        except (EOFError, KeyboardInterrupt):
            print("Exiting")
            break

        command = sanitize_input(raw_command)
        command = assistant._normalize_command(command)

        if debug_input:
            print(f"DEBUG input raw={raw_command!r} normalized={command!r}")

        if not command:
            continue

        if is_key_chord_artifact(command):
            continue

        if command.lower() in {"exit", "quit"}:
            print("Exiting")
            break

        try:
            response = assistant.process(command)
        except Exception as exc:
            logging.exception("Command processing failed for input: %s", command)
            response = f"Error processing command: {exc}"
        print(response)


def run_voice_mode():
    """Run wake-word voice mode with automation command execution."""
    from core.Assistant import EnhancedProfessionalAIAutomation
    from voice_engine import VoiceEngine

    jarvis = EnhancedProfessionalAIAutomation()
    wake_word = ConfigManager.get("JARVIS_WAKE_WORD", default="jarvis")
    model_path = ConfigManager.get("JARVIS_VOSK_MODEL_PATH", default="model")
    voice = VoiceEngine(model_path=model_path, wake_word=wake_word)

    print(f"Starting voice wake loop (wake word: {wake_word})")
    print("Say the wake word, then speak your command. Press Ctrl+C to stop.")

    def handle_voice(cmd: str) -> str:
        result = jarvis.process_command(cmd)
        return str(result)

    voice.handle_command = handle_voice

    try:
        voice.start()
        while True:
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("Stopping voice mode")
    finally:
        voice.stop()


def run_voice_live_mode():
    """Run direct microphone speech recognition loop with TTS responses."""
    from core.Assistant import EnhancedProfessionalAIAutomation
    from voice_assistant import VoiceAssistant

    jarvis = EnhancedProfessionalAIAutomation()
    assistant = VoiceAssistant(jarvis)
    print("Starting live voice mode. Say 'exit' to stop.")
    assistant.run()


def main():
    channels_started = False
    try:
        setup_logging()

        channels_started, channel_message = start_channel_services()
        if channels_started:
            logging.info(channel_message)
            print(channel_message)
        else:
            logging.info(channel_message)

        config_result = validate_config(load_config())
        warnings_text = render_validation_warnings(config_result)
        if warnings_text:
            print(warnings_text)

        if not ConfigManager.get_bool("JARVIS_SKIP_MIGRATION", default=False):
            migration_summary = migrate_legacy_data(PROJECT_ROOT)
            migration_text = render_migration_summary(migration_summary)
            if migration_text:
                print(migration_text)

        if "--check-apis" in sys.argv:
            results, masked = run_api_healthcheck(str(PROJECT_ROOT / ".env"))
            print(render_health_report(results, masked))
            return

        if "--voice" in sys.argv:
            run_voice_mode()
            return

        if "--voice-brain" in sys.argv:
            from core.Assistant import EnhancedProfessionalAIAutomation

            jarvis = EnhancedProfessionalAIAutomation()
            jarvis.start_voice_mode()
            return

        if "--voice-live" in sys.argv:
            run_voice_live_mode()
            return

        force_console = "--console" in sys.argv
        env_ui = ConfigManager.get("JARVIS_UI", default="").lower()
        use_gui = not force_console
        if env_ui in {"gui", "console"}:
            use_gui = env_ui == "gui"

        if "--gui" in sys.argv:
            use_gui = True

        if use_gui and sys.platform.startswith("linux"):
            has_x11 = bool(os.getenv("DISPLAY"))
            has_wayland = bool(os.getenv("WAYLAND_DISPLAY"))
            if not has_x11 and not has_wayland:
                logging.warning("No DISPLAY/WAYLAND_DISPLAY detected; forcing console mode")
                print("No desktop session detected; starting in safe console mode")
                use_gui = False

        if use_gui:
            try:
                if sys.platform.startswith("linux"):
                    session_type = (ConfigManager.get("XDG_SESSION_TYPE", default="") or "").lower()
                    is_wayland_session = session_type == "wayland" and bool(
                        ConfigManager.get("WAYLAND_DISPLAY", default="")
                    )
                    prefer_wayland = ConfigManager.get_bool("JARVIS_QT_PREFER_WAYLAND", default=False)
                    if (
                        prefer_wayland
                        and is_wayland_session
                    ):
                        os.environ.setdefault("QT_QPA_PLATFORM", "wayland")
                    else:
                        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

                    if is_wayland_session:
                        os.environ.setdefault("JARVIS_AUTH_SHOW_PREVIEW", "0")
                    chromium_flags = ConfigManager.get("QTWEBENGINE_CHROMIUM_FLAGS", default="").strip()
                    required_flags = [
                        "--no-sandbox",
                        "--autoplay-policy=no-user-gesture-required",
                        "--allow-file-access-from-files",
                        "--unsafely-treat-insecure-origin-as-secure=file://",
                    ]
                    if ConfigManager.get_bool("JARVIS_GUI_SAFE_MODE", default=True):
                        os.environ.setdefault("QT_OPENGL", "software")
                        os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
                        safe_flags = [
                            "--disable-gpu",
                            "--disable-gpu-compositing",
                            "--disable-dev-shm-usage",
                            "--disable-features=UseSkiaRenderer,VizDisplayCompositor",
                        ]
                        required_flags.extend(safe_flags)
                    for flag in required_flags:
                        if flag not in chromium_flags:
                            chromium_flags = f"{chromium_flags} {flag}".strip()
                    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = chromium_flags
                    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
                    _normalize_qt_env()

                if not _qt_gui_preflight():
                    logging.warning("Qt GUI preflight failed; forcing console mode")
                    print("GUI dependencies unavailable; falling back to safe console mode")
                    use_gui = False

                if not use_gui:
                    print("Starting assistant in safe console mode")
                    run_console()
                    return
                print("Starting assistant in GUI mode")
                from gui.main_window import main as gui_main

                exit_code = gui_main()
                if isinstance(exit_code, int) and exit_code != 0:
                    logging.warning("GUI exited with non-zero code: %s", exit_code)
                return
            except Exception as exc:
                logging.exception("GUI failed to start")
                print(f"GUI failed to start: {exc}")
                print("Falling back to console mode")

        print("Starting assistant in safe console mode")
        run_console()
    except Exception as exc:
        logging.exception("Fatal startup error")
        print(f"Fatal startup error: {exc}")
    finally:
        if channels_started:
            stop_channel_services()


if __name__ == "__main__":
    main()
    