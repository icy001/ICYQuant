"""Lineage Edge — relationships between LineageNodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class EdgeType(Enum):
    """Semantic relationship types between lineage nodes."""

    GENERATED = auto()          # Strategy → Signal
    CAUSED = auto()             # Signal → Decision
    EVALUATED_BY = auto()       # Decision → RiskDecision
    CONSTRAINED_BY = auto()     # RiskDecision → GovernanceDecision
    AUTHORIZED_BY = auto()      # GovernanceDecision → AuthorityDecision
    APPROVED_BY = auto()        # AuthorityDecision → Approval
    ADMITTED_AS = auto()        # Approval → OrderIntent
    CERTIFIED_BY = auto()       # OrderIntent → Certificate
    CREATED = auto()            # Certificate → Order
    EXECUTED_AS = auto()        # Order → Execution
    RESULTED_IN = auto()        # Execution → Trade
    UPDATED = auto()            # Trade → Position
    POSTED_TO = auto()          # Position → LedgerEvent
    ADMITTED = auto()           # OrderIntent → Admission
    ISSUED = auto()             # Admission → Certificate

    @property
    def label(self) -> str:
        _labels: dict[EdgeType, str] = {
            EdgeType.GENERATED: "generated",
            EdgeType.CAUSED: "caused",
            EdgeType.EVALUATED_BY: "evaluated by",
            EdgeType.CONSTRAINED_BY: "constrained by",
            EdgeType.AUTHORIZED_BY: "authorized by",
            EdgeType.APPROVED_BY: "approved by",
            EdgeType.ADMITTED_AS: "admitted as",
            EdgeType.CERTIFIED_BY: "certified by",
            EdgeType.CREATED: "created",
            EdgeType.EXECUTED_AS: "executed as",
            EdgeType.RESULTED_IN: "resulted in",
            EdgeType.UPDATED: "updated",
            EdgeType.POSTED_TO: "posted to",
            EdgeType.ADMITTED: "admitted",
            EdgeType.ISSUED: "issued",
        }
        return _labels.get(self, self.name)


# Expected edge sequence for the standard control-to-execution chain.
EXPECTED_EDGE_SEQUENCE: list[EdgeType] = [
    EdgeType.GENERATED,
    EdgeType.CAUSED,
    EdgeType.EVALUATED_BY,
    EdgeType.CONSTRAINED_BY,
    EdgeType.AUTHORIZED_BY,
    EdgeType.APPROVED_BY,
    EdgeType.ADMITTED_AS,
    EdgeType.ADMITTED,
    EdgeType.ISSUED,
    EdgeType.CERTIFIED_BY,
    EdgeType.CREATED,
    EdgeType.EXECUTED_AS,
    EdgeType.RESULTED_IN,
]


@dataclass
class LineageEdge:
    """A directed edge connecting two LineageNodes."""

    edge_id: str = field(
        default_factory=lambda: (
            f"EDGE-{__import__('uuid').uuid4().hex[:12].upper()}"
        ),
    )
    from_node_id: str = ""
    to_node_id: str = ""
    edge_type: EdgeType = EdgeType.CAUSED
    lineage_id: str = ""
    timestamp: float = field(
        default_factory=lambda: __import__("time").time(),
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return self.edge_type.label

    @property
    def key(self) -> str:
        """Unique compound key for deduplication."""
        return f"{self.from_node_id}|{self.edge_type.name}|{self.to_node_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "from_node_id": self.from_node_id,
            "to_node_id": self.to_node_id,
            "edge_type": self.edge_type.name,
            "lineage_id": self.lineage_id,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def create(cls, from_node_id: str, to_node_id: str,
               edge_type: EdgeType, lineage_id: str,
               metadata: dict[str, Any] | None = None,
               ) -> "LineageEdge":
        """Factory for a new edge."""
        import time as _t
        return cls(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            edge_type=edge_type,
            lineage_id=lineage_id,
            timestamp=_t.time(),
            metadata=metadata or {},
        )
