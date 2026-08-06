"""Edge definition model — connection between workflow nodes."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class EdgeType(str, enum.Enum):
    """Types of edges in a workflow DAG."""

    NORMAL = "normal"
    CONDITIONAL = "conditional"
    DEFAULT = "default"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class EdgeDefinition:
    """Immutable edge definition — directed connection between two nodes."""

    edge_id: str
    source_id: str
    target_id: str
    edge_type: EdgeType = EdgeType.NORMAL
    condition: Optional[str] = None
    label: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_type": self.edge_type.value,
            "condition": self.condition,
            "label": self.label,
            "metadata": self.metadata,
            "weight": self.weight,
        }

    def __repr__(self) -> str:
        return (
            f"EdgeDefinition(edge_id={self.edge_id!r}, "
            f"{self.source_id} -> {self.target_id}, type={self.edge_type.value})"
        )
