"""OMS error hierarchy."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        # order_errors
        "OrderError": ".order_errors",
        "OrderNotFoundError": ".order_errors",
        "OrderNotAcceptedError": ".order_errors",
        "OrderCertificateError": ".order_errors",
        "OrderLineageError": ".order_errors",
        "OrderIdempotencyError": ".order_errors",
        "OrderQuantityInconsistencyError": ".order_errors",
        "ParentQuantityExceededError": ".order_errors",
        "ConcurrentModificationError": ".order_errors",
        "OrderValidationError": ".order_errors",
        # lifecycle_errors
        "LifecycleError": ".lifecycle_errors",
        "InvalidStateTransitionError": ".lifecycle_errors",
        "TerminalStateModificationError": ".lifecycle_errors",
        "UnknownExecutionStateError": ".lifecycle_errors",
        "ExecutionTimeoutError": ".lifecycle_errors",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "OrderError",
    "OrderNotFoundError",
    "OrderNotAcceptedError",
    "OrderCertificateError",
    "OrderLineageError",
    "OrderIdempotencyError",
    "OrderQuantityInconsistencyError",
    "ParentQuantityExceededError",
    "ConcurrentModificationError",
    "OrderValidationError",
    "LifecycleError",
    "InvalidStateTransitionError",
    "TerminalStateModificationError",
    "UnknownExecutionStateError",
    "ExecutionTimeoutError",
]
