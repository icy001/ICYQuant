"""Lineage Node — the fundamental unit of a control lineage graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class NodeType(Enum):
    """Kinds of entities that can appear as nodes in a control lineage."""

    STRATEGY = auto()
    SIGNAL = auto()
    DECISION = auto()
    RISK_DECISION = auto()
    GOVERNANCE_DECISION = auto()
    AUTHORITY_DECISION = auto()
    APPROVAL = auto()
    ORDER_INTENT = auto()
    ADMISSION = auto()
    CERTIFICATE = auto()
    ORDER = auto()
    EXECUTION = auto()
    TRADE = auto()
    POSITION = auto()
    LEDGER_EVENT = auto()

    @property
    def label(self) -> str:
        """Human-readable label for the node type."""
        _labels: dict[NodeType, str] = {
            NodeType.STRATEGY: "Strategy",
            NodeType.SIGNAL: "Signal",
            NodeType.DECISION: "Decision",
            NodeType.RISK_DECISION: "Risk Decision",
            NodeType.GOVERNANCE_DECISION: "Governance Decision",
            NodeType.AUTHORITY_DECISION: "Authority Decision",
            NodeType.APPROVAL: "Approval",
            NodeType.ORDER_INTENT: "Order Intent",
            NodeType.ADMISSION: "Admission",
            NodeType.CERTIFICATE: "Certificate",
            NodeType.ORDER: "Order",
            NodeType.EXECUTION: "Execution",
            NodeType.TRADE: "Trade",
            NodeType.POSITION: "Position",
            NodeType.LEDGER_EVENT: "Ledger Event",
        }
        return _labels.get(self, self.name)

    @property
    def is_control_node(self) -> bool:
        """Whether this node type belongs to the control layer."""
        return self in {
            NodeType.RISK_DECISION,
            NodeType.GOVERNANCE_DECISION,
            NodeType.AUTHORITY_DECISION,
            NodeType.APPROVAL,
        }

    @property
    def is_execution_node(self) -> bool:
        """Whether this node type belongs to the execution layer."""
        return self in {
            NodeType.ORDER,
            NodeType.EXECUTION,
            NodeType.TRADE,
        }


@dataclass
class LineageNode:
    """A single node in the control lineage graph.

    Every key domain object (Strategy, Decision, Certificate, Order,
    Execution, Trade) is represented as a LineageNode.  Nodes are
    connected by LineageEdges to form the full audit trail.
    """

    node_id: str = field(
        default_factory=lambda: (
            f"NODE-{__import__('uuid').uuid4().hex[:12].upper()}"
        ),
    )
    node_type: NodeType = NodeType.DECISION
    lineage_id: str = ""

    # ── Reference fields ──────────────────────────────────────────
    object_id: str = ""
    """The ID of the domain object this node represents (e.g. 'DEC-001')."""

    flow_id: str = ""
    """The business flow ID. Multiple flow_ids may belong to one lineage."""

    parent_node_id: str = ""
    """Immediate parent node in the lineage graph (for upward traversal)."""

    # ── Timing ────────────────────────────────────────────────────
    timestamp: float = field(
        default_factory=lambda: __import__("time").time(),
    )

    # ── Extras ────────────────────────────────────────────────────
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ────────────────────────────────────────────────

    @property
    def is_control(self) -> bool:
        return self.node_type.is_control_node

    @property
    def is_execution(self) -> bool:
        return self.node_type.is_execution_node

    # ── Serialization ─────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.name,
            "lineage_id": self.lineage_id,
            "object_id": self.object_id,
            "flow_id": self.flow_id,
            "parent_node_id": self.parent_node_id,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def create(cls, node_type: NodeType, object_id: str,
               lineage_id: str, parent_node_id: str = "",
               flow_id: str = "",
               metadata: dict[str, Any] | None = None,
               ) -> "LineageNode":
        """Factory for a node pointing to a domain object."""
        import time as _t
        return cls(
            node_type=node_type,
            object_id=object_id,
            lineage_id=lineage_id,
            parent_node_id=parent_node_id,
            flow_id=flow_id,
            timestamp=_t.time(),
            metadata=metadata or {},
        )


# ── Deterministic node-type ordering for forward traversal ──────────

NODE_TYPE_ORDER: dict[NodeType, int] = {
    NodeType.STRATEGY: 0,
    NodeType.SIGNAL: 1,
    NodeType.DECISION: 2,
    NodeType.RISK_DECISION: 3,
    NodeType.GOVERNANCE_DECISION: 4,
    NodeType.AUTHORITY_DECISION: 5,
    NodeType.APPROVAL: 6,
    NodeType.ORDER_INTENT: 7,
    NodeType.ADMISSION: 8,
    NodeType.CERTIFICATE: 9,
    NodeType.ORDER: 10,
    NodeType.EXECUTION: 11,
    NodeType.TRADE: 12,
    NodeType.POSITION: 13,
    NodeType.LEDGER_EVENT: 14,
}
