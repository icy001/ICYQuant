"""Lineage lifecycle events — recorded transitions on nodes/edges."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class LifecycleEventType(Enum):
    """Types of lifecycle events on lineage artifacts."""

    NODE_CREATED = auto()
    NODE_UPDATED = auto()
    NODE_EXPIRED = auto()
    NODE_REVOKED = auto()
    NODE_COMPLETED = auto()
    EDGE_ADDED = auto()
    EDGE_REMOVED = auto()
    LINEAGE_STARTED = auto()
    LINEAGE_COMPLETED = auto()
    LINEAGE_FROZEN = auto()

    @property
    def label(self) -> str:
        _labels: dict[LifecycleEventType, str] = {
            LifecycleEventType.NODE_CREATED: "Node Created",
            LifecycleEventType.NODE_UPDATED: "Node Updated",
            LifecycleEventType.NODE_EXPIRED: "Node Expired",
            LifecycleEventType.NODE_REVOKED: "Node Revoked",
            LifecycleEventType.NODE_COMPLETED: "Node Completed",
            LifecycleEventType.EDGE_ADDED: "Edge Added",
            LifecycleEventType.EDGE_REMOVED: "Edge Removed",
            LifecycleEventType.LINEAGE_STARTED: "Lineage Started",
            LifecycleEventType.LINEAGE_COMPLETED: "Lineage Completed",
            LifecycleEventType.LINEAGE_FROZEN: "Lineage Frozen",
        }
        return _labels.get(self, self.name)


@dataclass
class LineageEvent:
    """A lifecycle event on a lineage artifact.

    Represents creation, modification, or lifecycle transitions of
    nodes and edges within a control lineage.
    """

    event_id: str = field(
        default_factory=lambda: (
            f"LEV-{__import__('uuid').uuid4().hex[:12].upper()}"
        ),
    )
    node_id: str = ""
    event_type: LifecycleEventType = LifecycleEventType.NODE_CREATED
    lineage_id: str = ""
    timestamp: float = field(
        default_factory=lambda: __import__("time").time(),
    )
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "node_id": self.node_id,
            "event_type": self.event_type.name,
            "lineage_id": self.lineage_id,
            "timestamp": self.timestamp,
            "payload": dict(self.payload),
        }
