"""
Lineage Node — a single node in the decision lineage graph.

Each node represents one state/entity in the full decision chain:
  MARKET → SIGNAL → STRATEGY → DECISION → POLICY → AUTHORITY
  → APPROVAL → ORDER → EXECUTION → TRADE → POSITION → LEDGER
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class LineageNodeType(Enum):
    """All node types in the ICYQuant decision lineage graph."""

    MARKET = auto()
    FACTOR = auto()
    SIGNAL = auto()
    STRATEGY = auto()
    DECISION = auto()
    POLICY = auto()
    RISK = auto()
    ALLOCATION = auto()
    AUTHORITY = auto()
    DELEGATION = auto()
    APPROVAL = auto()
    DECISION_GUARD = auto()
    CERTIFICATE = auto()
    ORDER = auto()
    EXECUTION = auto()
    TRADE = auto()
    POSITION = auto()
    LEDGER = auto()
    HUMAN_OVERRIDE = auto()
    EMERGENCY_ACTION = auto()

    @property
    def is_source(self) -> bool:
        """Whether this node type is a source (no incoming edges)."""
        return self in (LineageNodeType.MARKET, LineageNodeType.HUMAN_OVERRIDE)

    @property
    def is_sink(self) -> bool:
        """Whether this node type is a sink (no outgoing edges)."""
        return self in (LineageNodeType.LEDGER, LineageNodeType.POSITION)


@dataclass
class LineageNode:
    """A node in the decision lineage graph.

    Each node captures:
      - What entity it represents
      - Its full state at the time of recording
      - A hash of that state for integrity verification
    """

    node_id: str
    node_type: LineageNodeType
    entity_type: str   # e.g. "DECISION", "POLICY", "ORDER"
    entity_id: str     # e.g. "DEC-001", "POLICY-CAPITAL-001"
    label: str = ""

    # State snapshot
    state: Dict[str, Any] = field(default_factory=dict)
    state_hash: str = ""

    # Attribution
    correlation_id: str = ""
    timestamp: float = field(default_factory=time.time)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.name,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "label": self.label or f"{self.entity_type}:{self.entity_id}",
            "state": self.state,
            "state_hash": self.state_hash,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LineageNode":
        node_type = data.get("node_type", "DECISION")
        if isinstance(node_type, str):
            node_type = LineageNodeType[node_type]
        return cls(
            node_id=data.get("node_id", ""),
            node_type=node_type,
            entity_type=data.get("entity_type", ""),
            entity_id=data.get("entity_id", ""),
            label=data.get("label", ""),
            state=data.get("state", {}),
            state_hash=data.get("state_hash", ""),
            correlation_id=data.get("correlation_id", ""),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
        )

    # ── Factory ──

    @classmethod
    def create(
        cls,
        node_type: LineageNodeType,
        entity_type: str,
        entity_id: str,
        state: Optional[Dict[str, Any]] = None,
        correlation_id: str = "",
        label: str = "",
    ) -> "LineageNode":
        return cls(
            node_id=f"NODE-{uuid.uuid4().hex[:12].upper()}",
            node_type=node_type,
            entity_type=entity_type,
            entity_id=entity_id,
            label=label or f"{entity_type}:{entity_id}",
            state=state or {},
            correlation_id=correlation_id,
        )
