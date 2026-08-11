"""OMS domain layer — Order aggregate, value objects, and lifecycle."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "Order": ".order",
        "OrderId": ".order_id",
        "OrderStatus": ".order_status",
        "OrderSide": ".order_side",
        "OrderType": ".order_type",
        "TimeInForce": ".time_in_force",
        "OrderQuantity": ".order_quantity",
        "OrderPrice": ".order_price",
        "OrderLifecycle": ".order_lifecycle",
        "OrderLifecycleEvent": ".order_lifecycle",
        "LifecycleEventType": ".order_lifecycle",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "Order",
    "OrderId",
    "OrderStatus",
    "OrderSide",
    "OrderType",
    "TimeInForce",
    "OrderQuantity",
    "OrderPrice",
    "OrderLifecycle",
    "OrderLifecycleEvent",
    "LifecycleEventType",
]
