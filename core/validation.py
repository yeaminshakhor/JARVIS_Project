from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse


_ALLOWED_URL_SCHEMES = {"http", "https"}


def validate_url(url: str, allowlist: set[str] | None = None) -> bool:
    parsed = urlparse((url or "").strip())
    if parsed.scheme.lower() not in _ALLOWED_URL_SCHEMES:
        return False
    if not parsed.netloc:
        return False
    if allowlist:
        host = parsed.netloc.split(":", 1)[0].lower()
        return host in {x.lower() for x in allowlist}
    return True


def validate_filename(name: str, max_len: int = 120) -> bool:
    if not name or len(name) > max_len:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+", name))


def validate_user_name(value: str, max_len: int = 64) -> bool:
    value = (value or "").strip()
    if not value or len(value) > max_len:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9 _.-]+", value))


def validate_shell_fragment(value: str) -> bool:
    lowered = (value or "").lower()
    blocked = [";", "&&", "||", "`", "$(", "rm -rf", "mkfs", "shutdown", "reboot"]
    return not any(token in lowered for token in blocked)


def validate_path_in_base(path: str | Path, base_dir: str | Path) -> bool:
    try:
        p = Path(path).resolve()
        base = Path(base_dir).resolve()
        p.relative_to(base)
        return True
    except Exception:
        return False
