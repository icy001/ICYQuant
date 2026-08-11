"""OMS reconciliation package — order and execution reconciliation."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "OrderReconciler": ".order_reconciler",
        "ExecutionReconciler": ".execution_reconciler",
        "ReconciliationResult": ".reconciliation_result",
        "ReconciliationStatus": ".reconciliation_status",
        "Mismatch": ".mismatch",
        "MismatchSeverity": ".mismatch_severity",
        "MismatchType": ".mismatch",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "OrderReconciler", "ExecutionReconciler",
    "ReconciliationResult", "ReconciliationStatus",
    "Mismatch", "MismatchSeverity", "MismatchType",
]
