"""OMS recovery package — order state reconstruction from events."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "OrderRebuilder": ".order_rebuilder",
        "OrderRecovery": ".order_recovery",
        "RecoveryResult": ".order_recovery",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "OrderRebuilder",
    "OrderRecovery",
    "RecoveryResult",
]
