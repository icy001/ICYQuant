"""OMS events package — order event sourcing foundation."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "OrderEvent": ".order_event",
        "OrderEventType": ".order_event_type",
        "OrderEventMetadata": ".order_event_metadata",
        "OrderEventSequence": ".order_event_sequence",
        "OrderEventFactory": ".order_event_factory",
        "OrderEventSerializer": ".order_event_serializer",
        "OrderEventValidator": ".order_event_validator",
        "OrderEventError": ".order_event_errors",
        "EventSequenceGapError": ".order_event_errors",
        "DuplicateEventError": ".order_event_errors",
        "EventHashChainError": ".order_event_errors",
        "EventConcurrencyConflictError": ".order_event_errors",
        "EventCollisionError": ".order_event_errors",
        "EventValidationError": ".order_event_errors",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "OrderEvent",
    "OrderEventType",
    "OrderEventMetadata",
    "OrderEventSequence",
    "OrderEventFactory",
    "OrderEventSerializer",
    "OrderEventValidator",
    "OrderEventError",
    "EventSequenceGapError",
    "DuplicateEventError",
    "EventHashChainError",
    "EventConcurrencyConflictError",
    "EventCollisionError",
    "EventValidationError",
]
