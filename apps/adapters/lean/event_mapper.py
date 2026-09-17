"""LEAN event stream → ICYQuant event envelope.

Every event crossing the boundary gets the same envelope
(``{"type": ..., "payload": ...}``) so the consumer dispatches on one
field and never has to sniff LEAN-specific shapes.

An unknown event type is forwarded as ``UNKNOWN`` *with its payload
intact* rather than dropped: silently discarding an event we do not yet
understand is how a reconciliation gap is born.
"""
from __future__ import annotations

from typing import Any

from .order_mapper import map_order_event
from .position_mapper import map_lean_position

__all__ = ["map_lean_event"]

EXECUTION_EVENT_TYPES = frozenset({"ORDER", "ORDER_EVENT", "FILL"})


def map_lean_event(event: dict[str, Any]) -> dict[str, Any]:
    """Wrap one raw LEAN event in the ICYQuant envelope."""
    event_type = str(event.get("type", "")).upper()

    if event_type in EXECUTION_EVENT_TYPES:
        return {
            "type": "EXECUTION",
            "payload": map_order_event(event),
        }

    if event_type == "POSITION":
        return {
            "type": "POSITION",
            "payload": map_lean_position(event),
        }

    if event_type == "ERROR":
        return {
            "type": "ERROR",
            "payload": event,
        }

    return {
        "type": "UNKNOWN",
        "payload": event,
    }
