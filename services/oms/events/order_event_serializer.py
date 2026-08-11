"""OrderEventSerializer — JSON serialization for order events."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from .order_event import OrderEvent


class OrderEventSerializer:
    """Serializes and deserializes OrderEvent to/from JSON."""

    @staticmethod
    def to_dict(event: OrderEvent) -> Dict[str, Any]:
        return event.to_dict()

    @staticmethod
    def to_json(event: OrderEvent) -> str:
        return json.dumps(event.to_dict(), sort_keys=True, default=str)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> OrderEvent:
        return OrderEvent.from_dict(d)

    @staticmethod
    def from_json(json_str: str) -> OrderEvent:
        return OrderEvent.from_dict(json.loads(json_str))

    @staticmethod
    def to_json_list(events: List[OrderEvent]) -> str:
        return json.dumps(
            [e.to_dict() for e in events],
            sort_keys=True, default=str,
        )

    @staticmethod
    def from_json_list(json_str: str) -> List[OrderEvent]:
        data = json.loads(json_str)
        return [OrderEvent.from_dict(d) for d in data]
