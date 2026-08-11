"""OMS dead_letter package — dead-letter queue for unprocessable messages."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "DeadLetterEntry": ".dead_letter_entry",
        "DeadLetterStore": ".dead_letter_store",
        "DeadLetterManager": ".dead_letter_manager",
        "DeadLetterStatus": ".dead_letter_entry",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "DeadLetterEntry", "DeadLetterStore", "DeadLetterManager",
    "DeadLetterStatus",
]
