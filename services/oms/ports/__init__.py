"""OMS ports — abstract interfaces for persistence and external systems."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "OrderRepository": ".order_repository",
        "InMemoryOrderRepository": ".order_repository",
        "OrderEventStore": ".order_event_store",
        "InMemoryOrderEventStore": ".order_event_store",
        "ExecutionGateway": ".execution_gateway",
        "InMemoryExecutionGateway": ".execution_gateway",
        "ExecutionResult": ".execution_gateway",
        "ExecutionStatus": ".execution_gateway",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "OrderRepository",
    "InMemoryOrderRepository",
    "OrderEventStore",
    "InMemoryOrderEventStore",
    "ExecutionGateway",
    "InMemoryExecutionGateway",
    "ExecutionResult",
    "ExecutionStatus",
]
