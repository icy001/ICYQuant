"""
Lineage Reconstructor — reconstructs lineage graphs from snapshots and audit logs.

Can rebuild a complete lineage graph from:
  1. A DecisionRecord + its snapshot
  2. A sequence of AuditEvents with correlation_id
  3. A LineageSnapshot
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .lineage_graph import LineageGraph
from .lineage_node import LineageNode, LineageNodeType
from .lineage_edge import LineageEdge, LineageEdgeType
from .lineage_snapshot import LineageSnapshot


class LineageReconstructor:
    """Reconstructs lineage graphs from stored data.

    Supports reconstruction from:
      - AuditEvent sequences (by correlation_id)
      - DecisionRecord snapshots
      - LineageSnapshots
    """

    def __init__(self):
        self._graph: Optional[LineageGraph] = None

    # ── From Audit Events ──

    def reconstruct_from_events(
        self, events: List[Any],  # List[AuditEvent]
    ) -> LineageGraph:
        """Reconstruct a lineage graph from a sequence of AuditEvents.

        Maps audit events to lineage nodes based on entity_type.
        Connects nodes using correlation_id / causation_id.
        """
        graph = LineageGraph()
        self._graph = graph

        # Map entity_type → LineageNodeType
        type_map = {
            "MARKET": LineageNodeType.MARKET,
            "SIGNAL": LineageNodeType.SIGNAL,
            "FACTOR": LineageNodeType.FACTOR,
            "STRATEGY": LineageNodeType.STRATEGY,
            "DECISION": LineageNodeType.DECISION,
            "POLICY": LineageNodeType.POLICY,
            "RISK": LineageNodeType.RISK,
            "ALLOCATION": LineageNodeType.ALLOCATION,
            "AUTHORITY": LineageNodeType.AUTHORITY,
            "DELEGATION": LineageNodeType.DELEGATION,
            "APPROVAL": LineageNodeType.APPROVAL,
            "ORDER": LineageNodeType.ORDER,
            "EXECUTION": LineageNodeType.EXECUTION,
            "TRADE": LineageNodeType.TRADE,
            "POSITION": LineageNodeType.POSITION,
            "LEDGER": LineageNodeType.LEDGER,
        }

        # Group by correlation_id
        prev_node_id: Optional[str] = None

        for event in sorted(events, key=lambda e: e.timestamp):
            node_type = type_map.get(event.entity_type, LineageNodeType.DECISION)

            node = LineageNode.create(
                node_type=node_type,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                state={
                    "event_type": event.event_type.name,
                    "outcome": event.outcome.name,
                    "reason": event.reason,
                    "actor": event.actor.actor_id,
                },
                correlation_id=event.correlation_id,
            )
            graph.add_node(node)

            # Connect to previous node in same correlation
            if prev_node_id and event.causation_id:
                edge_type = LineageEdgeType.GENERATED
                if event.entity_type == "POLICY":
                    edge_type = LineageEdgeType.EVALUATED_BY
                elif event.entity_type == "AUTHORITY":
                    edge_type = LineageEdgeType.AUTHORIZED_BY
                elif event.entity_type == "APPROVAL":
                    edge_type = LineageEdgeType.APPROVED_BY

                graph.connect(prev_node_id, node.node_id, edge_type)

            prev_node_id = node.node_id

        return graph

    # ── From DecisionRecord ──

    def reconstruct_from_record(self, record: Any) -> LineageGraph:
        """Reconstruct a lineage graph from a DecisionRecord.

        Extracts nodes from the record's snapshot and creates
        the full chain: DECISION → POLICY → AUTHORITY → APPROVAL → EXECUTION.
        """
        graph = LineageGraph()
        self._graph = graph

        prev_node_id: Optional[str] = None

        # Decision node
        d_node = LineageNode.create(
            node_type=LineageNodeType.DECISION,
            entity_type="DECISION",
            entity_id=record.decision_id,
            state={"type": record.decision_type, "status": record.status.name},
            correlation_id=record.correlation_id,
        )
        graph.add_node(d_node)
        prev_node_id = d_node.node_id

        # Policy node
        if record.policy_id:
            p_node = LineageNode.create(
                node_type=LineageNodeType.POLICY,
                entity_type="POLICY",
                entity_id=record.policy_id,
                state={"version": record.policy_version, "verdict": record.policy_verdict},
                correlation_id=record.correlation_id,
            )
            graph.add_node(p_node)
            graph.connect(prev_node_id, p_node.node_id, LineageEdgeType.EVALUATED_BY)
            prev_node_id = p_node.node_id

        # Authority node
        if record.authority_id:
            a_node = LineageNode.create(
                node_type=LineageNodeType.AUTHORITY,
                entity_type="AUTHORITY",
                entity_id=record.authority_id,
                state={"delegation_id": record.delegation_id},
                correlation_id=record.correlation_id,
            )
            graph.add_node(a_node)
            graph.connect(prev_node_id, a_node.node_id, LineageEdgeType.AUTHORIZED_BY)
            prev_node_id = a_node.node_id

        # Approval node
        if record.approval_id:
            ap_node = LineageNode.create(
                node_type=LineageNodeType.APPROVAL,
                entity_type="APPROVAL",
                entity_id=record.approval_id,
                state={"status": record.approval_status},
                correlation_id=record.correlation_id,
            )
            graph.add_node(ap_node)
            graph.connect(prev_node_id, ap_node.node_id, LineageEdgeType.APPROVED_BY)
            prev_node_id = ap_node.node_id

        # Execution/trade
        if record.trade_id:
            t_node = LineageNode.create(
                node_type=LineageNodeType.TRADE,
                entity_type="TRADE",
                entity_id=record.trade_id,
                state={"instrument": record.instrument, "amount": record.amount},
                correlation_id=record.correlation_id,
            )
            graph.add_node(t_node)
            graph.connect(prev_node_id, t_node.node_id, LineageEdgeType.EXECUTED_AS)

        return graph

    # ── From Snapshot ──

    def reconstruct_from_snapshot(self, snapshot: LineageSnapshot) -> LineageGraph:
        """Reconstruct a lineage graph from a LineageSnapshot."""
        graph = LineageGraph()
        self._graph = graph

        # Add nodes
        for node_data in snapshot.nodes:
            node = LineageNode.from_dict(node_data)
            graph.add_node(node)

        # Add edges
        for edge_data in snapshot.edges:
            edge = LineageEdge.from_dict(edge_data)
            try:
                graph.add_edge(edge)
            except ValueError:
                pass  # Missing nodes

        return graph

    def get_graph(self) -> Optional[LineageGraph]:
        return self._graph
