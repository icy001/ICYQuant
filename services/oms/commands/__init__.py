"""OMS commands package — command definitions for order processing."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "OrderCommand": ".order_command",
        "CommandMetadata": ".command_metadata",
        "CreateOrderCommand": ".create_order",
        "StartRoutingCommand": ".start_routing",
        "MarkWorkingCommand": ".mark_working",
        "ApplyExecutionCommand": ".apply_execution",
        "RequestCancelCommand": ".request_cancel",
        "ConfirmCancelCommand": ".confirm_cancel",
        "RejectOrderCommand": ".reject_order",
        "ExpireOrderCommand": ".expire_order",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "OrderCommand",
    "CommandMetadata",
    "CreateOrderCommand",
    "StartRoutingCommand",
    "MarkWorkingCommand",
    "ApplyExecutionCommand",
    "RequestCancelCommand",
    "ConfirmCancelCommand",
    "RejectOrderCommand",
    "ExpireOrderCommand",
]
