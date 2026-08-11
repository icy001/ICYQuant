"""OMS event_store package — durable append-only event storage."""
from __future__ import annotations

import importlib


def __getattr__(name: str):
    _imports = {
        "OrderEventStore": ".order_event_store",
        "InMemoryOrderEventStore": ".order_event_store",
        "EventStream": ".event_stream",
        "EventStreamReader": ".event_stream_reader",
        "EventStreamWriter": ".event_stream_writer",
        "EventStoreSnapshot": ".event_store_snapshot",
        "EventStoreError": ".event_store_errors",
        "EventStreamNotFoundError": ".event_store_errors",
        "EventStreamClosedError": ".event_store_errors",
        "SnapshotValidationError": ".event_store_errors",
    }
    if name in _imports:
        mod = importlib.import_module(_imports[name], __package__)
        return getattr(mod, name)
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )


__all__ = [
    "OrderEventStore",
    "InMemoryOrderEventStore",
    "EventStream",
    "EventStreamReader",
    "EventStreamWriter",
    "EventStoreSnapshot",
    "EventStoreError",
    "EventStreamNotFoundError",
    "EventStreamClosedError",
    "SnapshotValidationError",
]
