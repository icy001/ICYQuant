"""Lineage Builder — fluent builder for control lineage graphs.

Builds a complete LineageGraph step-by-step from Strategy through Trade,
mirroring the ICYQuant institutional control flow.
"""

from __future__ import annotations

from typing import Any

from .lineage_node import LineageNode, NodeType
from .lineage_edge import LineageEdge, EdgeType
from .lineage_graph import LineageGraph
from .lineage_snapshot import DecisionSnapshot
from .lineage_errors import LineageIntegrityError


class LineageBuilder:
    """Fluent builder that constructs a LineageGraph incrementally.

    Usage::

        graph = (
            LineageBuilder("LINEAGE-001")
            .start_with_strategy("STRAT-007")
            .emit_signal("SIG-381")
            .emit_decision("DEC-091")
            .with_risk_decision(True, ...)
            .with_governance_decision(True, ...)
            .with_authority_decision(True, ...)
            .with_approval(True, ...)
            .with_order_intent("INTENT-001", ...)
            .with_admission(True, ...)
            .with_certificate(True, ...)
            .emit_order("ORDER-001")
            .emit_execution("EXEC-001")
            .emit_trade("TRADE-001")
            .build()
        )
    """

    def __init__(self, lineage_id: str = "") -> None:
        self._lineage_id: str = lineage_id or (
            f"LINEAGE-{__import__('uuid').uuid4().hex[:12].upper()}"
        )
        self._nodes: list[LineageNode] = []
        self._edges: list[LineageEdge] = []
        self._snapshots: dict[str, DecisionSnapshot] = {}
        self._last_node_id: str = ""
        self._decision_node_id: str = ""

    # ── Node helpers ──────────────────────────────────────────────

    def _add_node(self, node_type: NodeType, object_id: str,
                  metadata: dict[str, Any] | None = None,
                  ) -> LineageNode:
        parent = self._last_node_id
        node = LineageNode.create(
            node_type=node_type,
            object_id=object_id,
            lineage_id=self._lineage_id,
            parent_node_id=parent,
            metadata=metadata or {},
        )
        self._nodes.append(node)
        self._last_node_id = node.node_id
        return node

    def _add_edge(self, from_id: str, to_id: str,
                  edge_type: EdgeType,
                  metadata: dict[str, Any] | None = None,
                  ) -> LineageEdge:
        edge = LineageEdge.create(
            from_node_id=from_id,
            to_node_id=to_id,
            edge_type=edge_type,
            lineage_id=self._lineage_id,
            metadata=metadata or {},
        )
        self._edges.append(edge)
        return edge

    def _link_last_to(self, to_id: str,
                      edge_type: EdgeType) -> LineageEdge:
        # The 'from' is the penultimate node (the one before what we
        # just added).  _add_node already pushed the new node, so
        # _nodes[-2] is the source and _nodes[-1] is the target.
        if len(self._nodes) >= 2:
            from_id = self._nodes[-2].node_id
        elif self._nodes:
            from_id = self._nodes[-1].node_id
        else:
            from_id = ""
        return self._add_edge(from_id, to_id, edge_type)

    # ── Step 0: Strategy ──────────────────────────────────────────

    def start_with_strategy(self, strategy_id: str,
                            **meta: Any) -> "LineageBuilder":
        """Begin a lineage from a Strategy."""
        node = self._add_node(NodeType.STRATEGY, strategy_id, dict(meta))
        return self

    # ── Step 1: Signal ────────────────────────────────────────────

    def emit_signal(self, signal_id: str,
                    **meta: Any) -> "LineageBuilder":
        """Add a Signal node, linked from the current Strategy."""
        node = self._add_node(NodeType.SIGNAL, signal_id, dict(meta))
        self._link_last_to(node.node_id, EdgeType.GENERATED)
        return self

    # ── Step 2: Decision ──────────────────────────────────────────

    def emit_decision(self, decision_id: str,
                      decision_type: str = "",
                      decision_reason: str = "",
                      **meta: Any) -> "LineageBuilder":
        """Add a Decision node."""
        node = self._add_node(NodeType.DECISION, decision_id, dict(meta))
        self._link_last_to(node.node_id, EdgeType.CAUSED)
        self._decision_node_id = node.node_id

        # auto-create a snapshot
        snap = DecisionSnapshot.for_decision(
            lineage_id=self._lineage_id,
            node_id=node.node_id,
            decision_type=decision_type,
            decision_reason=decision_reason,
        )
        self._snapshots[node.node_id] = snap
        return self

    # ── Step 3: Risk ──────────────────────────────────────────────

    def with_risk_decision(self, passed: bool,
                           policy_version: str = "",
                           risk_exposure: float = 0.0,
                           risk_limit: float = 0.0,
                           available_margin: float = 0.0,
                           **meta: Any) -> "LineageBuilder":
        """Add a Risk Decision node."""
        node = self._add_node(
            NodeType.RISK_DECISION,
            f"RISK-{__import__('uuid').uuid4().hex[:8].upper()}",
            dict(passed=passed, policy_version=policy_version, **meta),
        )
        self._link_last_to(node.node_id, EdgeType.EVALUATED_BY)

        # enrich snapshot
        decision_node_id = self._decision_node_id
        snap = self._snapshots.get(decision_node_id)
        if snap:
            snap.risk_exposure = risk_exposure
            snap.risk_limit = risk_limit
            snap.available_margin = available_margin
            snap.risk_policy_version = policy_version

        if not passed:
            raise LineageIntegrityError(
                "Risk gate did not pass — cannot proceed in lineage",
                self._lineage_id,
            )
        return self

    # ── Step 4: Governance ────────────────────────────────────────

    def with_governance_decision(self, passed: bool,
                                 state: str = "NORMAL",
                                 policy_version: str = "",
                                 **meta: Any) -> "LineageBuilder":
        """Add a Governance Decision node."""
        node = self._add_node(
            NodeType.GOVERNANCE_DECISION,
            f"GOV-{__import__('uuid').uuid4().hex[:8].upper()}",
            dict(passed=passed, state=state, policy_version=policy_version, **meta),
        )
        self._link_last_to(node.node_id, EdgeType.CONSTRAINED_BY)

        decision_node_id = self._decision_node_id
        snap = self._snapshots.get(decision_node_id)
        if snap:
            snap.governance_state = state
            snap.governance_policy_version = policy_version

        if not passed:
            raise LineageIntegrityError(
                "Governance gate did not pass — cannot proceed in lineage",
                self._lineage_id,
            )
        return self

    # ── Step 5: Authority ─────────────────────────────────────────

    def with_authority_decision(self, passed: bool,
                                authority_id: str = "",
                                limit: float = 0.0,
                                requested: float = 0.0,
                                policy_version: str = "",
                                **meta: Any) -> "LineageBuilder":
        """Add an Authority Decision node."""
        node = self._add_node(
            NodeType.AUTHORITY_DECISION,
            f"AUTH-{__import__('uuid').uuid4().hex[:8].upper()}",
            dict(passed=passed, authority_id=authority_id,
                 limit=limit, requested=requested,
                 policy_version=policy_version, **meta),
        )
        self._link_last_to(node.node_id, EdgeType.AUTHORIZED_BY)

        decision_node_id = self._decision_node_id
        snap = self._snapshots.get(decision_node_id)
        if snap:
            snap.authority_limit = limit
            snap.authority_requested = requested
            snap.authority_policy_version = policy_version

        if not passed:
            raise LineageIntegrityError(
                "Authority gate did not pass — cannot proceed in lineage",
                self._lineage_id,
            )
        return self

    # ── Step 6: Approval ──────────────────────────────────────────

    def with_approval(self, passed: bool,
                      approval_id: str = "",
                      status: str = "APPROVED",
                      policy_version: str = "",
                      scope: str = "",
                      **meta: Any) -> "LineageBuilder":
        """Add an Approval node."""
        node_id = approval_id or (
            f"APR-{__import__('uuid').uuid4().hex[:8].upper()}"
        )
        node = self._add_node(
            NodeType.APPROVAL, node_id,
            dict(passed=passed, status=status,
                 policy_version=policy_version, scope=scope, **meta),
        )
        self._link_last_to(node.node_id, EdgeType.APPROVED_BY)

        decision_node_id = self._decision_node_id
        snap = self._snapshots.get(decision_node_id)
        if snap:
            snap.approval_id = node_id
            snap.approval_scope = scope
            snap.approval_policy_version = policy_version

        if not passed:
            raise LineageIntegrityError(
                "Approval did not pass — cannot proceed in lineage",
                self._lineage_id,
            )
        return self

    # ── Step 7: Order Intent ──────────────────────────────────────

    def with_order_intent(self, intent_id: str,
                          account_id: str = "",
                          symbol: str = "",
                          side: str = "",
                          **meta: Any) -> "LineageBuilder":
        """Add an Order Intent node."""
        node = self._add_node(
            NodeType.ORDER_INTENT, intent_id,
            dict(account_id=account_id, symbol=symbol, side=side, **meta),
        )
        self._link_last_to(node.node_id, EdgeType.ADMITTED_AS)
        return self

    # ── Step 8: Admission ─────────────────────────────────────────

    def with_admission(self, passed: bool,
                       admission_id: str = "",
                       **meta: Any) -> "LineageBuilder":
        """Add an Admission node."""
        aid = admission_id or (
            f"ADM-{__import__('uuid').uuid4().hex[:8].upper()}"
        )
        node = self._add_node(
            NodeType.ADMISSION, aid,
            dict(passed=passed, **meta),
        )
        self._link_last_to(node.node_id, EdgeType.ADMITTED)
        return self

    # ── Step 9: Certificate ───────────────────────────────────────

    def with_certificate(self, passed: bool,
                         certificate_id: str = "",
                         certificate_fingerprint: str = "",
                         **meta: Any) -> "LineageBuilder":
        """Add a Certificate node."""
        cert_id = certificate_id or (
            f"CERT-{__import__('uuid').uuid4().hex[:8].upper()}"
        )
        node = self._add_node(
            NodeType.CERTIFICATE, cert_id,
            dict(passed=passed,
                 certificate_fingerprint=certificate_fingerprint,
                 **meta),
        )
        self._link_last_to(node.node_id, EdgeType.CERTIFIED_BY)
        return self

    # ── Step 10: Order ────────────────────────────────────────────

    def emit_order(self, order_id: str,
                   **meta: Any) -> "LineageBuilder":
        """Add an Order node."""
        node = self._add_node(NodeType.ORDER, order_id, dict(meta))
        self._link_last_to(node.node_id, EdgeType.CREATED)
        return self

    # ── Step 11: Execution ────────────────────────────────────────

    def emit_execution(self, execution_id: str,
                       **meta: Any) -> "LineageBuilder":
        """Add an Execution node."""
        node = self._add_node(NodeType.EXECUTION, execution_id, dict(meta))
        self._link_last_to(node.node_id, EdgeType.EXECUTED_AS)
        return self

    # ── Step 12: Trade ────────────────────────────────────────────

    def emit_trade(self, trade_id: str,
                   **meta: Any) -> "LineageBuilder":
        """Add a Trade node."""
        node = self._add_node(NodeType.TRADE, trade_id, dict(meta))
        self._link_last_to(node.node_id, EdgeType.RESULTED_IN)
        return self

    # ── Additional helpers ────────────────────────────────────────

    def add_custom_node(self, node_type: NodeType, object_id: str,
                        edge_type: EdgeType,
                        **meta: Any) -> "LineageBuilder":
        """Add an arbitrary node with the given edge from the last node."""
        node = self._add_node(node_type, object_id, dict(meta))
        self._link_last_to(node.node_id, edge_type)
        return self

    def add_snapshot(self, node_id: str,
                     snapshot: DecisionSnapshot) -> "LineageBuilder":
        """Attach a decision snapshot to a node."""
        self._snapshots[node_id] = snapshot
        return self

    # ── Terminal ──────────────────────────────────────────────────

    def build(self) -> LineageGraph:
        """Assemble and return the complete LineageGraph."""
        graph = LineageGraph(lineage_id=self._lineage_id)
        for n in self._nodes:
            graph.add_node(n)
        for e in self._edges:
            graph.add_edge(e)
        return graph

    def get_snapshots(self) -> dict[str, DecisionSnapshot]:
        """Return all decision snapshots collected during the build."""
        return dict(self._snapshots)

    @property
    def lineage_id(self) -> str:
        return self._lineage_id
