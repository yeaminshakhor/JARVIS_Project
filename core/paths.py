from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "Data"
CACHE_DIR = DATA_DIR / "cache"
LOGS_DIR = DATA_DIR / "logs"
AUTH_DIR = DATA_DIR / "auth"
CONVERSATIONS_DIR = DATA_DIR / "conversations"
FRONTEND_DIR = PROJECT_ROOT / "Frontend"
FRONTEND_FILES_DIR = FRONTEND_DIR / "Files"
FRONTEND_GRAPHICS_DIR = FRONTEND_DIR / "Graphics"
FRONTEND_MEDIA_DIR = FRONTEND_DIR / "Media"
GRAPHICS_DIR = PROJECT_ROOT / "graphics"


def ensure_dirs() -> None:
    for directory in [
        DATA_DIR,
        CACHE_DIR,
        LOGS_DIR,
        AUTH_DIR,
        CONVERSATIONS_DIR,
        FRONTEND_DIR,
        FRONTEND_FILES_DIR,
        FRONTEND_GRAPHICS_DIR,
        FRONTEND_MEDIA_DIR,
        GRAPHICS_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)
