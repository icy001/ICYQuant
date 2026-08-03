"""Shared utility functions."""
from __future__ import annotations
import hashlib
import json
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional

def current_timestamp() -> str:
    return datetime.utcnow().isoformat() + "Z"

def generate_hash(data: str, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    h.update(data.encode("utf-8"))
    return h.hexdigest()

def sanitize_filename(filename: str) -> str:
    return "".join(c for c in filename if c.isalnum() or c in "._-()")

def deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result

def json_dumps(obj: Any, default: Optional[Callable] = None) -> str:
    return json.dumps(obj, indent=2, default=default, ensure_ascii=False)

def json_loads(data: str) -> Any:
    return json.loads(data)

def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
):
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(current_delay)
                        current_delay *= backoff
            raise last_exception
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

def env_var(name: str, default: Any = None, cast: Optional[type] = None) -> Any:
    value = os.environ.get(name)
    if value is None:
        return default
    if cast is not None:
        try:
            return cast(value)
        except (ValueError, TypeError):
            return default
    return value

def mask_sensitive(data: str, keep_start: int = 4, keep_end: int = 4) -> str:
    if len(data) <= keep_start + keep_end:
        return "*" * len(data)
    return data[:keep_start] + "*" * (len(data) - keep_start - keep_end) + data[-keep_end:]

def format_bytes(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

def timeit(func: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        return result
    wrapper.__name__ = func.__name__
    return wrapper
