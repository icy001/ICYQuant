"""OMS timeout package — execution timeout management."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "TimeoutPolicy": ".timeout_policy",
        "TimeoutManager": ".timeout_manager",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = ["TimeoutPolicy", "TimeoutManager"]
