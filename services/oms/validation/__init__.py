"""OMS validation package — command and state validators."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "CommandValidator": ".command_validator",
        "LifecycleValidator": ".lifecycle_validator",
        "QuantityValidator": ".quantity_validator",
        "ConcurrencyValidator": ".concurrency_validator",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "CommandValidator",
    "LifecycleValidator",
    "QuantityValidator",
    "ConcurrencyValidator",
]
