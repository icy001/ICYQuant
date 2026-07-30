"""ICYQuant Data Lineage.

End-to-end data lineage tracking from raw market data to trading decisions.

Tracks the complete data flow:
    Tick → 1min Bar → Return → EMA20 → Momentum → Alpha → Model → Trading Decision

Every data transformation, feature computation, and model inference is recorded,
enabling full audit trails and impact analysis.

Usage::

    tracker = LineageTracker(LineageConfig())
    tracker.add_node("market_tick", producer="market_data", operation="ingest")
    tracker.add_edge("market_tick", "1min_bar", transform="resample")
    chain = tracker.trace_downstream("market_tick")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from services.data_platform.config import LineageConfig


# ============================================================================
# Lineage Types
# ============================================================================


class OperationType(str, Enum):
    """Types of operations tracked in lineage."""

    INGEST = "ingest"            # Raw data ingestion
    TRANSFORM = "transform"       # Data transformation
    AGGREGATE = "aggregate"       # Aggregation / resampling
    JOIN = "join"                 # Data joining
    FILTER = "filter"             # Data filtering
    FEATURE = "feature"           # Feature computation
    FACTOR = "factor"             # Factor computation
    MODEL_TRAIN = "model_train"   # Model training
    MODEL_INFER = "model_infer"   # Model inference
    BACKTEST = "backtest"         # Backtest execution
    TRADE = "trade"               # Trade execution
    EXPORT = "export"             # Data export
    SNAPSHOT = "snapshot"         # Snapshot creation


@dataclass
class LineageNode:
    """A node in the data lineage graph.

    Represents a data asset at a point in the pipeline.
    """

    node_id: str
    dataset: str
    producer: str
    operation: OperationType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    row_count: int = 0
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "dataset": self.dataset,
            "producer": self.producer,
            "operation": self.operation.value,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "row_count": self.row_count,
            "description": self.description,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LineageNode":
        return cls(
            node_id=d["node_id"],
            dataset=d["dataset"],
            producer=d["producer"],
            operation=OperationType(d["operation"]),
            timestamp=datetime.fromisoformat(d["timestamp"]) if "timestamp" in d else datetime.utcnow(),
            version=d.get("version", 1),
            row_count=d.get("row_count", 0),
            description=d.get("description", ""),
            metadata=d.get("metadata", {}),
        )


@dataclass
class LineageEdge:
    """An edge in the data lineage graph.

    Represents a transformation from one dataset to another.
    """

    edge_id: str
    source_node: str
    target_node: str
    transform: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_node": self.source_node,
            "target_node": self.target_node,
            "transform": self.transform,
            "timestamp": self.timestamp.isoformat(),
            "description": self.description,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LineageEdge":
        return cls(
            edge_id=d["edge_id"],
            source_node=d["source_node"],
            target_node=d["target_node"],
            transform=d["transform"],
            timestamp=datetime.fromisoformat(d["timestamp"]) if "timestamp" in d else datetime.utcnow(),
            description=d.get("description", ""),
            metadata=d.get("metadata", {}),
        )


@dataclass
class LineageChain:
    """A complete lineage chain from source to target."""

    nodes: List[LineageNode] = field(default_factory=list)
    edges: List[LineageEdge] = field(default_factory=list)
    source_dataset: str = ""
    target_dataset: str = ""
    depth: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "source_dataset": self.source_dataset,
            "target_dataset": self.target_dataset,
            "depth": self.depth,
        }

    def get_path_description(self) -> str:
        """Get a human-readable description of the lineage chain."""
        if not self.nodes:
            return "Empty chain"

        parts = [n.dataset for n in self.nodes]
        return " → ".join(parts)


@dataclass
class ImpactAnalysis:
    """Impact analysis result for a dataset change."""

    dataset: str
    affected_downstream: List[str] = field(default_factory=list)
    affected_upstream: List[str] = field(default_factory=list)
    total_affected: int = 0
    severity: str = "low"  # low, medium, high, critical


# ============================================================================
# Lineage Tracker
# ============================================================================


class LineageTracker:
    """Data Lineage Tracker.

    Tracks the complete data flow from ingestion to trading decisions.
    Supports upstream tracing (where did this data come from?) and
    downstream impact analysis (what will this change affect?).

    Usage::

        tracker = LineageTracker()
        tracker.add_node("market_tick", producer="market_data", operation="ingest")
        tracker.add_node("1min_bar", producer="market_data", operation="aggregate")
        tracker.add_edge("market_tick", "1min_bar", transform="resample_1min")
        chain = tracker.trace_downstream("market_tick")
    """

    def __init__(self, config: Optional[LineageConfig] = None) -> None:
        self.config = config or LineageConfig()
        self._nodes: Dict[str, LineageNode] = {}
        self._edges: Dict[str, LineageEdge] = {}
        self._adjacency: Dict[str, Set[str]] = {}  # source → target
        self._reverse_adjacency: Dict[str, Set[str]] = {}  # target → source
        self._dataset_to_nodes: Dict[str, List[str]] = {}  # dataset → node_ids
        self._node_counter: int = 0
        self._edge_counter: int = 0

    # ------------------------------------------------------------------
    # Node Management
    # ------------------------------------------------------------------

    def add_node(
        self,
        dataset: str,
        producer: str,
        operation: OperationType,
        row_count: int = 0,
        description: str = "",
        **kwargs: Any,
    ) -> LineageNode:
        """Add a node to the lineage graph.

        Args:
            dataset: Dataset name.
            producer: Producer identifier (e.g. "market_data", "feature_pipeline").
            operation: Type of operation.
            row_count: Number of rows produced.
            description: Human-readable description.
            **kwargs: Additional metadata.

        Returns:
            Created LineageNode.
        """
        self._node_counter += 1
        node_id = f"node_{self._node_counter}"

        node = LineageNode(
            node_id=node_id,
            dataset=dataset,
            producer=producer,
            operation=operation,
            row_count=row_count,
            description=description,
            metadata=kwargs,
        )

        self._nodes[node_id] = node
        self._dataset_to_nodes.setdefault(dataset, []).append(node_id)
        self._adjacency.setdefault(node_id, set())
        self._reverse_adjacency.setdefault(node_id, set())

        return node

    def get_node(self, node_id: str) -> Optional[LineageNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def get_nodes_by_dataset(self, dataset: str) -> List[LineageNode]:
        """Get all nodes for a specific dataset."""
        node_ids = self._dataset_to_nodes.get(dataset, [])
        return [self._nodes[nid] for nid in node_ids if nid in self._nodes]

    # ------------------------------------------------------------------
    # Edge Management
    # ------------------------------------------------------------------

    def add_edge(
        self,
        source_dataset: str,
        target_dataset: str,
        transform: str,
        description: str = "",
        **kwargs: Any,
    ) -> Optional[LineageEdge]:
        """Add an edge between two datasets in the lineage graph.

        Args:
            source_dataset: Source dataset name.
            target_dataset: Target dataset name.
            transform: Transformation description (e.g. "resample_1min").
            description: Human-readable description.
            **kwargs: Additional metadata.

        Returns:
            Created LineageEdge, or None if source/target not found.
        """
        source_nodes = self._dataset_to_nodes.get(source_dataset, [])
        target_nodes = self._dataset_to_nodes.get(target_dataset, [])

        if not source_nodes or not target_nodes:
            return None

        # Use latest node for each dataset
        source_node_id = source_nodes[-1]
        target_node_id = target_nodes[-1]

        self._edge_counter += 1
        edge_id = f"edge_{self._edge_counter}"

        edge = LineageEdge(
            edge_id=edge_id,
            source_node=source_node_id,
            target_node=target_node_id,
            transform=transform,
            description=description,
            metadata=kwargs,
        )

        self._edges[edge_id] = edge
        self._adjacency.setdefault(source_node_id, set()).add(target_node_id)
        self._reverse_adjacency.setdefault(target_node_id, set()).add(source_node_id)

        return edge

    def get_edge(self, edge_id: str) -> Optional[LineageEdge]:
        """Get an edge by ID."""
        return self._edges.get(edge_id)

    # ------------------------------------------------------------------
    # Tracing
    # ------------------------------------------------------------------

    def trace_downstream(
        self,
        dataset: str,
        max_depth: Optional[int] = None,
    ) -> LineageChain:
        """Trace all downstream datasets from a source.

        "What depends on this data?"

        Args:
            dataset: Starting dataset name.
            max_depth: Maximum traversal depth (defaults to config).

        Returns:
            LineageChain with all downstream nodes and edges.
        """
        max_depth = max_depth or self.config.max_depth
        nodes: List[LineageNode] = []
        edges: List[LineageEdge] = []
        visited: Set[str] = set()

        node_ids = self._dataset_to_nodes.get(dataset, [])
        if not node_ids:
            return LineageChain(source_dataset=dataset, depth=0)

        # BFS traversal
        queue: List[Tuple[str, int]] = [(nid, 0) for nid in node_ids]
        max_depth_seen = 0

        while queue:
            current_id, current_depth = queue.pop(0)

            if current_id in visited or current_depth > max_depth:
                continue

            visited.add(current_id)
            max_depth_seen = max(max_depth_seen, current_depth)
            if current_id in self._nodes:
                nodes.append(self._nodes[current_id])

            # Follow edges
            for next_id in self._adjacency.get(current_id, set()):
                if next_id not in visited:
                    queue.append((next_id, current_depth + 1))
                    # Find the edge
                    for edge in self._edges.values():
                        if edge.source_node == current_id and edge.target_node == next_id:
                            edges.append(edge)
                            break

        return LineageChain(
            nodes=nodes,
            edges=edges,
            source_dataset=dataset,
            depth=max_depth_seen,
        )

    def trace_upstream(
        self,
        dataset: str,
        max_depth: Optional[int] = None,
    ) -> LineageChain:
        """Trace all upstream datasets to a target.

        "Where did this data come from?"

        Args:
            dataset: Target dataset name.
            max_depth: Maximum traversal depth.

        Returns:
            LineageChain with all upstream nodes and edges.
        """
        max_depth = max_depth or self.config.max_depth
        nodes: List[LineageNode] = []
        edges: List[LineageEdge] = []
        visited: Set[str] = set()

        node_ids = self._dataset_to_nodes.get(dataset, [])
        if not node_ids:
            return LineageChain(target_dataset=dataset, depth=0)

        # BFS reverse traversal
        queue: List[Tuple[str, int]] = [(nid, 0) for nid in node_ids]
        max_depth_seen = 0

        while queue:
            current_id, current_depth = queue.pop(0)

            if current_id in visited or current_depth > max_depth:
                continue

            visited.add(current_id)
            max_depth_seen = max(max_depth_seen, current_depth)
            if current_id in self._nodes:
                nodes.append(self._nodes[current_id])

            # Follow reverse edges
            for prev_id in self._reverse_adjacency.get(current_id, set()):
                if prev_id not in visited:
                    queue.append((prev_id, current_depth + 1))
                    # Find the edge
                    for edge in self._edges.values():
                        if edge.source_node == prev_id and edge.target_node == current_id:
                            edges.append(edge)
                            break

        return LineageChain(
            nodes=nodes,
            edges=edges,
            target_dataset=dataset,
            depth=max_depth_seen,
        )

    def get_lineage(self, dataset: str) -> List[LineageNode]:
        """Get all lineage nodes for a dataset (both directions)."""
        downstream = self.trace_downstream(dataset)
        upstream = self.trace_upstream(dataset)

        seen = {n.node_id for n in downstream.nodes}
        all_nodes = list(downstream.nodes)
        for node in upstream.nodes:
            if node.node_id not in seen:
                all_nodes.append(node)
                seen.add(node.node_id)

        return all_nodes

    # ------------------------------------------------------------------
    # Impact Analysis
    # ------------------------------------------------------------------

    def analyze_impact(self, dataset: str) -> ImpactAnalysis:
        """Analyze the impact of a change to a dataset.

        Determines what downstream datasets would be affected if this
        dataset changes.

        Args:
            dataset: Dataset name.

        Returns:
            ImpactAnalysis with affected datasets.
        """
        chain = self.trace_downstream(dataset)

        # Collect unique affected datasets
        affected = list({n.dataset for n in chain.nodes if n.dataset != dataset})

        # Determine severity
        severity = "low"
        if len(affected) > 20:
            severity = "critical"
        elif len(affected) > 10:
            severity = "high"
        elif len(affected) > 5:
            severity = "medium"

        # Also check upstream
        upstream_chain = self.trace_upstream(dataset)
        upstream_affected = list({
            n.dataset for n in upstream_chain.nodes if n.dataset != dataset
        })

        return ImpactAnalysis(
            dataset=dataset,
            affected_downstream=affected,
            affected_upstream=upstream_affected,
            total_affected=len(affected),
            severity=severity,
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def find_path(
        self,
        source_dataset: str,
        target_dataset: str,
    ) -> Optional[LineageChain]:
        """Find the lineage path between two datasets.

        Args:
            source_dataset: Source dataset.
            target_dataset: Target dataset.

        Returns:
            LineageChain if a path exists, None otherwise.
        """
        source_nodes = self._dataset_to_nodes.get(source_dataset, [])
        target_nodes = self._dataset_to_nodes.get(target_dataset, [])

        if not source_nodes or not target_nodes:
            return None

        start_id = source_nodes[-1]
        target_id = target_nodes[-1]

        # BFS to find path
        visited: Set[str] = set()
        parent: Dict[str, Optional[str]] = {start_id: None}
        queue: List[str] = [start_id]

        while queue:
            current = queue.pop(0)
            if current == target_id:
                break

            if current in visited:
                continue
            visited.add(current)

            for next_id in self._adjacency.get(current, set()):
                if next_id not in parent:
                    parent[next_id] = current
                    queue.append(next_id)

        if target_id not in parent:
            return None

        # Reconstruct path
        path_nodes: List[LineageNode] = []
        path_edges: List[LineageEdge] = []

        current = target_id
        while current is not None:
            if current in self._nodes:
                path_nodes.insert(0, self._nodes[current])

            prev = parent.get(current)
            if prev:
                for edge in self._edges.values():
                    if edge.source_node == prev and edge.target_node == current:
                        path_edges.insert(0, edge)
                        break

            current = prev  # type: ignore[assignment]

        return LineageChain(
            nodes=path_nodes,
            edges=path_edges,
            source_dataset=source_dataset,
            target_dataset=target_dataset,
            depth=len(path_nodes),
        )

    def get_graph_stats(self) -> Dict[str, Any]:
        """Get lineage graph statistics."""
        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "total_datasets": len(self._dataset_to_nodes),
            "operations": {
                op.value: sum(
                    1 for n in self._nodes.values() if n.operation == op
                )
                for op in OperationType
                if any(n.operation == op for n in self._nodes.values())
            },
            "producers": list({
                n.producer for n in self._nodes.values()
            }),
        }
