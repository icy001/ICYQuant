"""OMS repair package — repair actions for reconciliation mismatches."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "RepairManager": ".repair_manager",
        "RepairPolicy": ".repair_policy",
        "RepairAction": ".repair_action",
        "RepairActionType": ".repair_action",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "RepairManager", "RepairPolicy", "RepairAction", "RepairActionType",
]
