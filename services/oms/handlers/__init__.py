"""OMS handlers package — command handlers for order processing."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "CommandHandler": ".command_handler",
        "CreateOrderHandler": ".create_order_handler",
        "RoutingHandler": ".routing_handler",
        "ExecutionHandler": ".execution_handler",
        "CancellationHandler": ".cancellation_handler",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "CommandHandler",
    "CreateOrderHandler",
    "RoutingHandler",
    "ExecutionHandler",
    "CancellationHandler",
]
