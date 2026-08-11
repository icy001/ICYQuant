"""OMS application layer — services that orchestrate the order lifecycle."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "OrderService": ".order_service",
        "OrderAcceptor": ".order_acceptor",
        "OrderLifecycleManager": ".order_lifecycle_manager",
        "OrderStateMachine": ".order_state_machine",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "OrderService",
    "OrderAcceptor",
    "OrderLifecycleManager",
    "OrderStateMachine",
]
