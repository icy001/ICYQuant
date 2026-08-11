"""
Lineage Edge — a directed relationship between two lineage nodes.

Edge types define the nature of the relationship:
  GENERATED, USED, EVALUATED_BY, APPROVED_BY, EXECUTED_AS, etc.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class LineageEdgeType(Enum):
    """Types of relationships between lineage nodes."""

    GENERATED = auto()        # A generated B (e.g., Signal → Decision)
    USED = auto()             # A used B (e.g., Decision → Policy)
    EVALUATED_BY = auto()     # A was evaluated by B
    AUTHORIZED_BY = auto()    # A was authorized by B
    APPROVED_BY = auto()      # A was approved by B
    DELEGATED_BY = auto()     # A was delegated by B
    ALLOCATED_TO = auto()     # A was allocated to B
    CREATED_FROM = auto()     # A was created from B
    EXECUTED_AS = auto()      # A was executed as B
    SETTLED_TO = auto()       # A was settled to B
    CAUSED = auto()           # A caused B
    INVALIDATED_BY = auto()   # A was invalidated by B
    OVERRIDDEN_BY = auto()    # A was overridden by B
    DEPENDS_ON = auto()       # A depends on B
    VALIDATED_BY = auto()     # A was validated by B

    @property
    def is_causal(self) -> bool:
        """Whether this edge represents causation."""
        return self in (
            LineageEdgeType.GENERATED,
            LineageEdgeType.CAUSED,
            LineageEdgeType.CREATED_FROM,
        )

    @property
    def is_authority(self) -> bool:
        """Whether this edge represents authority flow."""
        return self in (
            LineageEdgeType.AUTHORIZED_BY,
            LineageEdgeType.APPROVED_BY,
            LineageEdgeType.DELEGATED_BY,
        )


@dataclass
class LineageEdge:
    """A directed edge connecting two lineage nodes."""

    edge_id: str
    edge_type: LineageEdgeType
    source_node_id: str   # From
    target_node_id: str   # To

    label: str = ""
    weight: float = 1.0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "edge_type": self.edge_type.name,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "label": self.label or self.edge_type.name,
            "weight": self.weight,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LineageEdge":
        edge_type = data.get("edge_type", "GENERATED")
        if isinstance(edge_type, str):
            edge_type = LineageEdgeType[edge_type]
        return cls(
            edge_id=data.get("edge_id", ""),
            edge_type=edge_type,
            source_node_id=data.get("source_node_id", ""),
            target_node_id=data.get("target_node_id", ""),
            label=data.get("label", ""),
            weight=data.get("weight", 1.0),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
        )

    # ── Factory ──

    @classmethod
    def create(
        cls,
        edge_type: LineageEdgeType,
        source_node_id: str,
        target_node_id: str,
    ) -> "LineageEdge":
        import uuid
        return cls(
            edge_id=f"EDGE-{uuid.uuid4().hex[:12].upper()}",
            edge_type=edge_type,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
        )
