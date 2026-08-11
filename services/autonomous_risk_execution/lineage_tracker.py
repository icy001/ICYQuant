"""
Lineage Tracker — complete decision lineage from alpha signal through risk
optimization to execution.

Provides full auditability and root-cause analysis by tracking every node
in the decision chain, enabling:
    - Reconstruction of the entire decision path for any entity
    - Root-cause analysis of rejected or suboptimal outcomes
    - Compliance reporting with full decision traceability
    - Performance attribution across the pipeline
    - Debugging of risk/execution failures

Each lineage chain captures:
    ALPHA_SIGNAL → TARGET_POSITION → RISK_OPTIMIZED → EXECUTION_PLAN →
    ORDER → FILL → FEEDBACK → ADJUSTMENT / REJECTION
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """Type of node in the decision lineage."""
    ALPHA_SIGNAL = "alpha_signal"
    TARGET_POSITION = "target_position"
    RISK_OPTIMIZED = "risk_optimized"
    EXECUTION_PLAN = "execution_plan"
    ORDER = "order"
    FILL = "fill"
    FEEDBACK = "feedback"
    ADJUSTMENT = "adjustment"
    REJECTION = "rejection"


class ChainStatus(Enum):
    """Status of a lineage chain."""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class LineageNode:
    """
    A single node in the decision lineage.

    Each node represents a discrete decision or state transition point
    in the pipeline from alpha signal through to execution outcome.

    Attributes:
        id: Unique node identifier.
        chain_id: The lineage chain this node belongs to.
        timestamp: When this node was created.
        node_type: The type of decision/event recorded.
        entity_id: The domain entity (e.g., symbol, order) this node relates to.
        description: Human-readable description of the decision.
        data: Arbitrary structured data associated with the node.
        confidence: Confidence score (0.0 to 1.0) for model-driven decisions.
        rationale: Explanation of why this decision was made.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    chain_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    node_type: NodeType = NodeType.ALPHA_SIGNAL
    entity_id: str = ""
    description: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    rationale: str = ""


@dataclass
class LineageEdge:
    """
    A directed edge connecting two nodes in the lineage.

    Edges represent causal or derived relationships between decisions,
    enabling reconstruction of the full decision graph.

    Attributes:
        id: Unique edge identifier.
        chain_id: The lineage chain this edge belongs to.
        from_node_id: The source node of the relationship.
        to_node_id: The target node of the relationship.
        edge_type: Classification of the relationship (e.g., "derived", "triggered", "caused").
        timestamp: When this edge was created.
        metadata: Additional context about the relationship.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    chain_id: str = ""
    from_node_id: str = ""
    to_node_id: str = ""
    edge_type: str = "derived"
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageChain:
    """
    A complete decision lineage chain from signal to outcome.

    Captures the full provenance of a trading decision, enabling
    auditability, reproducibility, and root-cause analysis.

    Attributes:
        id: Unique chain identifier.
        source: Originating source (e.g., "alpha_model", "rebalance", "manual").
        entity_id: The primary entity this chain tracks.
        status: Current status of the lineage chain.
        created_at: When the chain was started.
        completed_at: When the chain was finalized (None if still active).
        nodes: All nodes in the decision path.
        edges: All edges connecting nodes in the decision path.
        summary: Aggregated summary of the lineage outcome.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    source: str = ""
    entity_id: str = ""
    status: ChainStatus = ChainStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    nodes: list[LineageNode] = field(default_factory=list)
    edges: list[LineageEdge] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageStats:
    """
    Aggregated statistics across all lineage chains.

    Provides operational insights into the decision pipeline's
    volume, distribution, and timing characteristics.

    Attributes:
        total_chains: Total number of lineage chains tracked.
        active_chains: Number of currently active (in-progress) chains.
        completed_chains: Number of successfully completed chains.
        failed_chains: Number of chains that ended in failure or rejection.
        total_nodes: Total number of nodes across all chains.
        by_type: Node counts grouped by NodeType.
        avg_chain_length: Average number of nodes per completed chain.
        avg_duration_ms: Average chain duration in milliseconds.
    """
    total_chains: int = 0
    active_chains: int = 0
    completed_chains: int = 0
    failed_chains: int = 0
    total_nodes: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    avg_chain_length: float = 0.0
    avg_duration_ms: float = 0.0


class LineageTracker:
    """
    Tracks the complete decision lineage from alpha signal through risk
    optimization to execution, enabling full auditability and root-cause
    analysis.

    The LineageTracker maintains a directed graph of decisions for every
    entity that flows through the autonomous risk & execution pipeline.
    Each chain captures the full provenance of a trading decision, from
    the initial alpha signal through target position sizing, risk
    optimization, execution planning, order placement, fills, feedback,
    and any adjustments or rejections along the way.

    Key capabilities:
        - **Full Audit Trail**: Every decision is recorded with its
          rationale, confidence, and data context, satisfying regulatory
          requirements for decision traceability.
        - **Root-Cause Analysis**: When a trade is rejected, underperforms,
          or requires adjustment, the full lineage can be retraced to
          identify exactly where and why the outcome diverged from
          expectations.
        - **Decision Reconstruction**: Any lineage chain can be
          reconstructed to understand the complete decision path,
          including alternatives considered and confidence levels
          at each stage.
        - **Statistical Monitoring**: Aggregate statistics across all
          chains provide insight into pipeline throughput, decision
          quality, and bottleneck identification.

    Usage:
        tracker = LineageTracker()
        chain = await tracker.start_lineage(source="alpha_v2", entity_id="AAPL")

        node_id = await tracker.add_node(chain.id, LineageNode(
            node_type=NodeType.ALPHA_SIGNAL,
            entity_id="AAPL",
            description="Alpha signal generated",
            data={"score": 0.82},
            confidence=0.82,
        ))

        await tracker.complete_lineage(chain.id, final_status="completed")
        lineage = await tracker.get_lineage(chain.id)
    """

    def __init__(self) -> None:
        self._chains: dict[str, LineageChain] = {}
        self._node_index: dict[str, str] = {}  # node_id -> chain_id
        self._entity_index: dict[str, list[str]] = {}  # entity_id -> chain_ids
        self._decision_index: dict[str, str] = {}  # decision_id -> node_id

    async def start_lineage(self, source: str, entity_id: str) -> LineageChain:
        """
        Start a new lineage chain for a given entity.

        Initializes a new LineageChain in ACTIVE status, ready to
        accumulate nodes and edges as the decision progresses through
        the pipeline.

        Args:
            source: Originating source (e.g., "alpha_model", "rebalance").
            entity_id: The domain entity being tracked.

        Returns:
            The newly created LineageChain with a unique identifier.
        """
        chain = LineageChain(
            source=source,
            entity_id=entity_id,
            status=ChainStatus.ACTIVE,
        )
        self._chains[chain.id] = chain
        self._entity_index.setdefault(entity_id, []).append(chain.id)
        logger.info(
            "Lineage chain started: chain=%s source=%s entity=%s",
            chain.id, source, entity_id,
        )
        return chain

    async def add_node(self, chain_id: str, node: LineageNode) -> str:
        """
        Add a node to an existing lineage chain.

        Records a discrete decision or state transition point in the
        pipeline. The node is linked to the specified chain and indexed
        for fast lookup by entity and decision identifiers.

        Args:
            chain_id: The lineage chain to add the node to.
            node: The LineageNode to add; chain_id and timestamp are
                  overwritten with current values.

        Returns:
            The unique identifier of the added node.

        Raises:
            KeyError: If the specified chain_id does not exist.
        """
        chain = self._chains[chain_id]
        node.chain_id = chain_id
        if not node.timestamp:
            node.timestamp = datetime.now()
        chain.nodes.append(node)
        self._node_index[node.id] = chain_id
        if node.entity_id:
            self._entity_index.setdefault(node.entity_id, [])
            if chain_id not in self._entity_index[node.entity_id]:
                self._entity_index[node.entity_id].append(chain_id)
        logger.debug(
            "Lineage node added: chain=%s node=%s type=%s",
            chain_id, node.id, node.node_type.value,
        )
        return node.id

    async def add_edge(
        self,
        chain_id: str,
        from_node_id: str,
        to_node_id: str,
        edge_type: str = "derived",
    ) -> str:
        """
        Add a directed edge between two nodes in a lineage chain.

        Edges define causal or derived relationships between decisions,
        enabling reconstruction of the full decision graph for
        root-cause analysis.

        Args:
            chain_id: The lineage chain containing both nodes.
            from_node_id: The source node identifier.
            to_node_id: The target node identifier.
            edge_type: Classification of the relationship
                       (e.g., "derived", "triggered", "caused").

        Returns:
            The unique identifier of the added edge.

        Raises:
            KeyError: If the specified chain_id does not exist.
        """
        chain = self._chains[chain_id]
        edge = LineageEdge(
            chain_id=chain_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            edge_type=edge_type,
        )
        chain.edges.append(edge)
        logger.debug(
            "Lineage edge added: chain=%s edge=%s %s->%s type=%s",
            chain_id, edge.id, from_node_id, to_node_id, edge_type,
        )
        return edge.id

    async def complete_lineage(
        self, chain_id: str, final_status: str = "completed"
    ) -> None:
        """
        Finalize a lineage chain with a terminal status.

        Marks the chain as completed, failed, or cancelled, recording
        the completion timestamp. Once finalized, no new nodes or edges
        may be added to the chain.

        Args:
            chain_id: The lineage chain to finalize.
            final_status: Terminal status ("completed", "failed",
                          "cancelled").

        Raises:
            KeyError: If the specified chain_id does not exist.
            ValueError: If the final_status is not a valid ChainStatus.
        """
        chain = self._chains[chain_id]
        status_map = {s.value: s for s in ChainStatus}
        if final_status not in status_map:
            raise ValueError(
                f"Invalid final_status: {final_status}. "
                f"Must be one of: {list(status_map.keys())}"
            )
        chain.status = status_map[final_status]
        chain.completed_at = datetime.now()
        chain.summary = {
            "total_nodes": len(chain.nodes),
            "total_edges": len(chain.edges),
            "duration_ms": (
                (chain.completed_at - chain.created_at).total_seconds() * 1000
            ),
            "node_types": list({n.node_type.value for n in chain.nodes}),
        }
        logger.info(
            "Lineage chain completed: chain=%s status=%s nodes=%d",
            chain_id, final_status, len(chain.nodes),
        )

    async def get_lineage(self, chain_id: str) -> LineageChain:
        """
        Retrieve a complete lineage chain by its identifier.

        Returns the full LineageChain including all nodes, edges,
        and summary data. This is the primary method for audit
        reconstruction and root-cause analysis of a specific decision.

        Args:
            chain_id: The unique chain identifier.

        Returns:
            The complete LineageChain.

        Raises:
            KeyError: If the specified chain_id does not exist.
        """
        return self._chains[chain_id]

    async def get_entity_lineage(
        self, entity_id: str, limit: int = 10
    ) -> list[LineageChain]:
        """
        Retrieve recent lineage chains for a given entity.

        Returns the most recent lineage chains associated with an
        entity, ordered by creation time descending. Useful for
        reviewing the decision history of a specific symbol, order,
        or portfolio component.

        Args:
            entity_id: The domain entity identifier.
            limit: Maximum number of chains to return (default 10).

        Returns:
            A list of LineageChain objects, most recent first.
        """
        chain_ids = self._entity_index.get(entity_id, [])
        chains = [self._chains[cid] for cid in chain_ids if cid in self._chains]
        chains.sort(key=lambda c: c.created_at, reverse=True)
        return chains[:limit]

    async def get_full_chain(self, entity_id: str) -> list[LineageChain]:
        """
        Retrieve all lineage chains for a given entity.

        Returns every lineage chain associated with an entity,
        providing the complete decision history for comprehensive
        audit or research analysis.

        Args:
            entity_id: The domain entity identifier.

        Returns:
            A list of all LineageChain objects for the entity,
            ordered by creation time ascending.
        """
        chain_ids = self._entity_index.get(entity_id, [])
        chains = [self._chains[cid] for cid in chain_ids if cid in self._chains]
        chains.sort(key=lambda c: c.created_at)
        return chains

    async def trace_decision(self, decision_id: str) -> dict[str, Any]:
        """
        Trace the full lineage for a specific decision identifier.

        Starting from the node matching the given decision_id,
        traverses the lineage graph both forward and backward to
        reconstruct the complete decision context. This enables
        precise root-cause analysis by showing exactly how a
        decision was derived and what its downstream effects were.

        Args:
            decision_id: The identifier of the decision/node to trace.

        Returns:
            A dictionary containing:
                - node: The matching LineageNode.
                - chain_id: The lineage chain containing the node.
                - predecessors: All nodes that causally precede this
                  decision in the chain.
                - successors: All nodes that derive from this decision.
                - edges_in: Edges pointing into this node.
                - edges_out: Edges pointing out of this node.

        Raises:
            KeyError: If the decision_id is not found in any chain.
        """
        chain_id = self._node_index.get(decision_id)
        if not chain_id:
            raise KeyError(
                f"Decision {decision_id} not found in any lineage chain"
            )

        chain = self._chains[chain_id]
        node = next((n for n in chain.nodes if n.id == decision_id), None)
        if not node:
            raise KeyError(
                f"Node {decision_id} not found in chain {chain_id}"
            )

        edges_in = [e for e in chain.edges if e.to_node_id == decision_id]
        edges_out = [e for e in chain.edges if e.from_node_id == decision_id]

        pred_ids = {e.from_node_id for e in edges_in}
        succ_ids = {e.to_node_id for e in edges_out}

        predecessors = [n for n in chain.nodes if n.id in pred_ids]
        successors = [n for n in chain.nodes if n.id in succ_ids]

        return {
            "node": node,
            "chain_id": chain_id,
            "predecessors": predecessors,
            "successors": successors,
            "edges_in": edges_in,
            "edges_out": edges_out,
        }

    async def get_stats(self) -> LineageStats:
        """
        Compute and return aggregate lineage statistics.

        Calculates summary metrics across all lineage chains, providing
        operational insights into pipeline throughput, decision
        complexity, and timing. Useful for monitoring system health,
        identifying bottlenecks, and reporting to stakeholders.

        Returns:
            A LineageStats instance with:
                - total_chains: All chains tracked.
                - active_chains: Currently in-progress chains.
                - completed_chains: Successfully completed chains.
                - failed_chains: Chains ending in failure or rejection.
                - total_nodes: Sum of nodes across all chains.
                - by_type: Node counts grouped by NodeType.
                - avg_chain_length: Average nodes per completed chain.
                - avg_duration_ms: Average chain duration in milliseconds.
        """
        chains = list(self._chains.values())
        total = len(chains)
        active = sum(1 for c in chains if c.status == ChainStatus.ACTIVE)
        completed = sum(1 for c in chains if c.status == ChainStatus.COMPLETED)
        failed = sum(
            1 for c in chains
            if c.status in (ChainStatus.FAILED, ChainStatus.CANCELLED)
        )

        all_nodes = [n for c in chains for n in c.nodes]
        total_nodes = len(all_nodes)

        by_type: dict[str, int] = {}
        for n in all_nodes:
            key = n.node_type.value
            by_type[key] = by_type.get(key, 0) + 1

        completed_chains = [c for c in chains if c.completed_at is not None]
        if completed_chains:
            avg_length = sum(len(c.nodes) for c in completed_chains) / len(
                completed_chains
            )
            durations = [
                (c.completed_at - c.created_at).total_seconds() * 1000
                for c in completed_chains
                if c.completed_at
            ]
            avg_duration = sum(durations) / len(durations) if durations else 0.0
        else:
            avg_length = 0.0
            avg_duration = 0.0

        return LineageStats(
            total_chains=total,
            active_chains=active,
            completed_chains=completed,
            failed_chains=failed,
            total_nodes=total_nodes,
            by_type=by_type,
            avg_chain_length=avg_length,
            avg_duration_ms=avg_duration,
        )