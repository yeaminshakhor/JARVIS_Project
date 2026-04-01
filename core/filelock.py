from __future__ import annotations

import os
from contextlib import contextmanager


@contextmanager
def file_lock(lock_path: str):
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
    handle = open(lock_path, "a+")
    lock_size = 0x7FFFFFFF
    try:
        if os.name == "posix":
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        elif os.name == "nt":
            import msvcrt
            handle.seek(0)
            if handle.tell() == 0:
                handle.write("\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, lock_size)
        yield
    finally:
        try:
            if os.name == "posix":
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            elif os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, lock_size)
        except Exception:
            pass
        handle.close()
        try:
            os.unlink(lock_path)
        except Exception:
            pass
