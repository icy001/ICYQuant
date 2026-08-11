"""OMS recovery package — order state reconstruction and recovery management."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        # Part 1.2
        "OrderRebuilder": ".order_rebuilder",
        "OrderRecovery": ".order_recovery",
        "RecoveryResult": ".order_recovery",
        # Part 1.5
        "RecoveryManager": ".recovery_manager",
        "RecoveryJob": ".recovery_result",
        "RecoveryState": ".recovery_state",
        "RecoveryPolicy": ".recovery_policy",
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
    "RecoveryManager",
    "RecoveryJob",
    "RecoveryState",
    "RecoveryPolicy",
]
