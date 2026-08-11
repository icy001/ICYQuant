"""OMS observability package — metrics and health monitoring."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "OrderMetrics": ".order_metrics",
        "ExecutionMetrics": ".execution_metrics",
        "RecoveryMetrics": ".recovery_metrics",
        "ReconciliationMetrics": ".reconciliation_metrics",
        "OMSHealth": ".oms_health",
        "HealthStatus": ".oms_health",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "OrderMetrics", "ExecutionMetrics",
    "RecoveryMetrics", "ReconciliationMetrics",
    "OMSHealth", "HealthStatus",
]
