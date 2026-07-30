"""
Graph Database Infrastructure.

Persistent storage backend for the knowledge graph
with query and traversal support.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class StoredNode:
    """A node persisted in the graph database."""

    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    labels: List[str] = field(default_factory=list)  # e.g., ["Company", "Technology"]
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "labels": self.labels,
            "properties": self.properties,
        }


@dataclass
class StoredEdge:
    """An edge (relationship) persisted in the graph database."""

    edge_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    label: str = ""  # e.g., "SUPPLIER_OF", "COMPETITOR_OF"
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "label": self.label,
            "properties": self.properties,
        }


@dataclass
class GraphQueryResult:
    """Result of a graph query."""

    nodes: List[StoredNode] = field(default_factory=list)
    edges: List[StoredEdge] = field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0


@dataclass
class GraphDBConfig:
    """Configuration for the graph database."""

    max_nodes: int = 1000000
    max_edges: int = 10000000
    enable_auto_index: bool = True


# ── Graph Database ───────────────────────────────────────────────────────────

class GraphDatabase:
    """
    In-memory graph database backend.

    Supports:
    - Node storage with labels and properties
    - Edge storage with types and properties
    - Label-based indexing
    - Property-based filtering
    - Traversal queries
    """

    def __init__(self, config: Optional[GraphDBConfig] = None):
        self.config = config or GraphDBConfig()
        self._nodes: Dict[str, StoredNode] = {}
        self._edges: Dict[str, StoredEdge] = {}
        # Adjacency
        self._adj_out: Dict[str, Dict[str, List[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._adj_in: Dict[str, Dict[str, List[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        # Label index
        self._label_index: Dict[str, Set[str]] = defaultdict(set)

    # ── Node CRUD ────────────────────────────────────────────────────────────

    def create_node(
        self,
        labels: Optional[List[str]] = None,
        properties: Optional[Dict[str, Any]] = None,
        node_id: Optional[str] = None,
    ) -> StoredNode:
        """Create a node."""
        if len(self._nodes) >= self.config.max_nodes:
            raise RuntimeError(f"Max nodes ({self.config.max_nodes}) reached")

        node = StoredNode(
            node_id=node_id or str(uuid.uuid4()),
            labels=labels or [],
            properties=properties or {},
        )
        self._nodes[node.node_id] = node

        # Index by label
        if self.config.enable_auto_index:
            for label in node.labels:
                self._label_index[label].add(node.node_id)

        return node

    def get_node(self, node_id: str) -> Optional[StoredNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def update_node(
        self, node_id: str, properties: Dict[str, Any]
    ) -> Optional[StoredNode]:
        """Update node properties."""
        node = self._nodes.get(node_id)
        if node:
            node.properties.update(properties)
            node.updated_at = datetime.now(timezone.utc)
        return node

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and its edges."""
        if node_id not in self._nodes:
            return False

        node = self._nodes[node_id]

        # Remove from label indexes
        for label in node.labels:
            self._label_index[label].discard(node_id)

        # Remove all connected edges
        edges_to_remove = []
        for eid, edge in self._edges.items():
            if edge.source_id == node_id or edge.target_id == node_id:
                edges_to_remove.append(eid)

        for eid in edges_to_remove:
            self.delete_edge(eid)

        del self._nodes[node_id]
        return True

    def find_nodes(
        self,
        labels: Optional[List[str]] = None,
        properties: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> List[StoredNode]:
        """Find nodes by labels and/or properties."""
        candidates: Set[str] = set()

        if labels:
            label_sets = [
                self._label_index.get(lbl, set()) for lbl in labels
            ]
            if label_sets:
                candidates = label_sets[0].copy()
                for ls in label_sets[1:]:
                    candidates &= ls
        else:
            candidates = set(self._nodes.keys())

        results = []
        for nid in candidates:
            node = self._nodes.get(nid)
            if not node:
                continue
            if properties:
                if all(
                    node.properties.get(k) == v
                    for k, v in properties.items()
                ):
                    results.append(node)
            else:
                results.append(node)

        return results[:limit]

    # ── Edge CRUD ────────────────────────────────────────────────────────────

    def create_edge(
        self,
        source_id: str,
        target_id: str,
        label: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Optional[StoredEdge]:
        """Create an edge between two nodes."""
        if source_id not in self._nodes or target_id not in self._nodes:
            logger.warning(f"Invalid edge: source={source_id}, target={target_id}")
            return None

        if len(self._edges) >= self.config.max_edges:
            raise RuntimeError(f"Max edges ({self.config.max_edges}) reached")

        edge = StoredEdge(
            source_id=source_id,
            target_id=target_id,
            label=label,
            properties=properties or {},
        )
        self._edges[edge.edge_id] = edge
        self._adj_out[source_id][target_id].append(edge.edge_id)
        self._adj_in[target_id][source_id].append(edge.edge_id)

        return edge

    def get_edge(self, edge_id: str) -> Optional[StoredEdge]:
        """Get an edge by ID."""
        return self._edges.get(edge_id)

    def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge."""
        if edge_id not in self._edges:
            return False

        edge = self._edges[edge_id]

        # Clean adjacency
        src_adj = self._adj_out.get(edge.source_id, {})
        tgt_adj = self._adj_in.get(edge.target_id, {})

        if edge.target_id in src_adj:
            src_adj[edge.target_id] = [
                eid for eid in src_adj[edge.target_id] if eid != edge_id
            ]
        if edge.source_id in tgt_adj:
            tgt_adj[edge.source_id] = [
                eid for eid in tgt_adj[edge.source_id] if eid != edge_id
            ]

        del self._edges[edge_id]
        return True

    # ── Queries ──────────────────────────────────────────────────────────────

    def get_neighbors(
        self,
        node_id: str,
        edge_labels: Optional[List[str]] = None,
        direction: str = "both",
        limit: int = 100,
    ) -> GraphQueryResult:
        """Get neighbors of a node."""
        if node_id not in self._nodes:
            return GraphQueryResult()

        nodes: List[StoredNode] = []
        edges: List[StoredEdge] = []
        seen_nodes: Set[str] = {node_id}

        def collect_neighbors(
            adj: Dict[str, Dict[str, List[str]]]
        ) -> None:
            for neighbor_id, edge_ids in adj.get(node_id, {}).items():
                if neighbor_id in seen_nodes:
                    continue
                for eid in edge_ids:
                    edge = self._edges.get(eid)
                    if not edge:
                        continue
                    if edge_labels and edge.label not in edge_labels:
                        continue
                    neighbor = self._nodes.get(neighbor_id)
                    if neighbor:
                        nodes.append(neighbor)
                        edges.append(edge)
                        seen_nodes.add(neighbor_id)
                        break

        if direction in ("outgoing", "both"):
            collect_neighbors(self._adj_out)
        if direction in ("incoming", "both"):
            collect_neighbors(self._adj_in)

        return GraphQueryResult(
            nodes=nodes[:limit],
            edges=edges[:limit],
            node_count=len(nodes),
            edge_count=len(edges),
        )

    def get_edges_between(
        self, source_id: str, target_id: str
    ) -> List[StoredEdge]:
        """Get edges between two nodes."""
        edge_ids = self._adj_out.get(source_id, {}).get(target_id, [])
        return [self._edges[eid] for eid in edge_ids if eid in self._edges]

    def path_exists(
        self, source_id: str, target_id: str, max_depth: int = 5
    ) -> bool:
        """Check if a path exists between two nodes."""
        if source_id not in self._nodes or target_id not in self._nodes:
            return False

        visited: Set[str] = {source_id}
        current_level = [source_id]

        for _ in range(max_depth):
            next_level = []
            for nid in current_level:
                for neighbor_id in self._adj_out.get(nid, {}):
                    if neighbor_id == target_id:
                        return True
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        next_level.append(neighbor_id)
            current_level = next_level
            if not current_level:
                break

        return False

    # ── Stats ────────────────────────────────────────────────────────────────

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def get_stats(self) -> Dict[str, Any]:
        label_counts = defaultdict(int)
        for node in self._nodes.values():
            for label in node.labels:
                label_counts[label] += 1

        edge_label_counts = defaultdict(int)
        for edge in self._edges.values():
            edge_label_counts[edge.label] += 1

        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "node_labels": dict(label_counts),
            "edge_labels": dict(edge_label_counts),
        }

    def clear(self) -> None:
        """Clear all data."""
        self._nodes.clear()
        self._edges.clear()
        self._adj_out.clear()
        self._adj_in.clear()
        self._label_index.clear()
