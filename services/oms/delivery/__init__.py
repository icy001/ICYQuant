"""OMS delivery package — request delivery and retry management."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "DeliveryManager": ".delivery_manager",
        "DeliveryAttempt": ".delivery_attempt",
        "DeliveryPolicy": ".delivery_policy",
        "DeliveryState": ".delivery_state",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = ["DeliveryManager", "DeliveryAttempt", "DeliveryPolicy", "DeliveryState"]
