"""OMS projection package — read models derived from events."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "OrderProjector": ".order_projector",
        "OrderStateReducer": ".order_state_reducer",
        "OrderProjection": ".order_projection",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "OrderProjector",
    "OrderStateReducer",
    "OrderProjection",
]
