from __future__ import annotations

import json
import time
from pathlib import Path

from .paths import CACHE_DIR, DATA_DIR


def clean_cache_dir(cache_dir: Path, ttl_seconds: int = 86400, max_files: int = 500) -> dict:
    cache_dir.mkdir(parents=True, exist_ok=True)
    now = time.time()
    removed = 0
    kept_files: list[tuple[Path, float]] = []

    for file in cache_dir.glob("*.json"):
        if not file.is_file():
            continue
        try:
            mtime = file.stat().st_mtime
        except Exception:
            continue
        if now - mtime > ttl_seconds:
            try:
                file.unlink(missing_ok=True)
                removed += 1
            except Exception:
                pass
            continue
        kept_files.append((file, mtime))

    kept_files.sort(key=lambda row: row[1], reverse=True)
    for file, _ in kept_files[max_files:]:
        try:
            file.unlink(missing_ok=True)
            removed += 1
        except Exception:
            continue

    remaining = max(0, min(len(kept_files), max_files))
    return {"directory": str(cache_dir), "remaining": remaining, "removed": removed}


def clean_all() -> list[dict]:
    targets = [
        CACHE_DIR,
        CACHE_DIR / "audio_collection",
        DATA_DIR / "model_cache",
        DATA_DIR / "search_cache",
    ]
    results = []
    for target in targets:
        results.append(clean_cache_dir(Path(target), ttl_seconds=86400, max_files=500))
    return results


if __name__ == "__main__":
    print(json.dumps(clean_all(), indent=2))
