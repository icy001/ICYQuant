"""
Lineage Graph — the complete directed graph of decision lineage.

Stores all nodes and edges for the full decision chain:
  MARKET → SIGNAL → STRATEGY → DECISION → ... → LEDGER

Supports graph operations: add/remove nodes and edges,
upstream/downstream traversal, subgraph extraction.
"""

from __future__ import annotations

import time
import threading
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from .lineage_node import LineageNode, LineageNodeType
from .lineage_edge import LineageEdge, LineageEdgeType


class LineageGraph:
    """Directed graph of decision lineage nodes and edges.

    Thread-safe. Supports:
      - Adding/removing nodes and edges
      - Upstream/downstream traversal
      - Subgraph extraction by correlation_id
      - Orphan detection
    """

    def __init__(self, max_nodes: int = 100_000):
        self._nodes: Dict[str, LineageNode] = {}
        self._edges: Dict[str, LineageEdge] = {}
        self._adj_in: Dict[str, Set[str]] = defaultdict(set)   # node_id → incoming edge_ids
        self._adj_out: Dict[str, Set[str]] = defaultdict(set)  # node_id → outgoing edge_ids
        self._lock = threading.Lock()
        self._max_nodes = max_nodes

    # ── Node Operations ──

    def add_node(self, node: LineageNode) -> LineageNode:
        with self._lock:
            if len(self._nodes) >= self._max_nodes:
                raise RuntimeError(f"LineageGraph full: {self._max_nodes} nodes")
            self._nodes[node.node_id] = node
            if node.node_id not in self._adj_in:
                self._adj_in[node.node_id] = set()
            if node.node_id not in self._adj_out:
                self._adj_out[node.node_id] = set()
            return node

    def get_node(self, node_id: str) -> Optional[LineageNode]:
        return self._nodes.get(node_id)

    def get_nodes_by_type(self, node_type: LineageNodeType) -> List[LineageNode]:
        return [n for n in self._nodes.values() if n.node_type == node_type]

    def get_nodes_by_entity(self, entity_type: str, entity_id: str) -> List[LineageNode]:
        return [
            n for n in self._nodes.values()
            if n.entity_type == entity_type and n.entity_id == entity_id
        ]

    def get_nodes_by_correlation(self, correlation_id: str) -> List[LineageNode]:
        return [n for n in self._nodes.values() if n.correlation_id == correlation_id]

    def find_root_nodes(self) -> List[LineageNode]:
        """Nodes with no incoming edges."""
        return [n for nid, n in self._nodes.items() if not self._adj_in.get(nid)]

    def find_leaf_nodes(self) -> List[LineageNode]:
        """Nodes with no outgoing edges."""
        return [n for nid, n in self._nodes.items() if not self._adj_out.get(nid)]

    # ── Edge Operations ──

    def add_edge(self, edge: LineageEdge) -> LineageEdge:
        with self._lock:
            if edge.source_node_id not in self._nodes:
                raise ValueError(f"Source node not found: {edge.source_node_id}")
            if edge.target_node_id not in self._nodes:
                raise ValueError(f"Target node not found: {edge.target_node_id}")

            self._edges[edge.edge_id] = edge
            self._adj_out[edge.source_node_id].add(edge.edge_id)
            self._adj_in[edge.target_node_id].add(edge.edge_id)
            return edge

    def get_edge(self, edge_id: str) -> Optional[LineageEdge]:
        return self._edges.get(edge_id)

    def get_edges_between(self, source_id: str, target_id: str) -> List[LineageEdge]:
        result: List[LineageEdge] = []
        for edge_id in self._adj_out.get(source_id, set()):
            edge = self._edges.get(edge_id)
            if edge and edge.target_node_id == target_id:
                result.append(edge)
        return result

    # ── Connect (convenience) ──

    def connect(
        self,
        source_node_id: str,
        target_node_id: str,
        edge_type: LineageEdgeType,
    ) -> LineageEdge:
        """Create and add an edge between two existing nodes."""
        edge = LineageEdge.create(edge_type, source_node_id, target_node_id)
        return self.add_edge(edge)

    # ── Traversal ──

    def get_upstream(self, node_id: str, max_depth: int = 20) -> List[LineageNode]:
        """Get all ancestor nodes (what led to this node)."""
        visited: Set[str] = set()
        result: List[LineageNode] = []
        self._traverse_upstream(node_id, visited, result, 0, max_depth)
        return result

    def get_downstream(self, node_id: str, max_depth: int = 20) -> List[LineageNode]:
        """Get all descendant nodes (what this node led to)."""
        visited: Set[str] = set()
        result: List[LineageNode] = []
        self._traverse_downstream(node_id, visited, result, 0, max_depth)
        return result

    def get_full_lineage(self, node_id: str, max_depth: int = 20) -> Dict[str, Any]:
        """Get full lineage: upstream + node + downstream."""
        node = self.get_node(node_id)
        upstream = self.get_upstream(node_id, max_depth)
        downstream = self.get_downstream(node_id, max_depth)
        return {
            "node": node.to_dict() if node else None,
            "upstream": [n.to_dict() for n in upstream],
            "downstream": [n.to_dict() for n in downstream],
            "upstream_count": len(upstream),
            "downstream_count": len(downstream),
        }

    def get_subgraph_by_correlation(self, correlation_id: str) -> "LineageGraph":
        """Extract a subgraph containing all nodes/edges for a correlation_id."""
        sub = LineageGraph()
        nodes = self.get_nodes_by_correlation(correlation_id)
        node_ids = {n.node_id for n in nodes}
        for n in nodes:
            sub.add_node(n)
        for e in self._edges.values():
            if e.source_node_id in node_ids and e.target_node_id in node_ids:
                sub.add_edge(e)
        return sub

    # ── Path ──

    def find_path_between(
        self, source_id: str, target_id: str, max_depth: int = 20
    ) -> Optional[List[LineageNode]]:
        """Find a path from source to target node."""
        if source_id not in self._nodes or target_id not in self._nodes:
            return None
        if source_id == target_id:
            return [self._nodes[source_id]]

        visited: Set[str] = {source_id}
        from collections import deque
        queue = deque([(source_id, [self._nodes[source_id]])])

        while queue:
            current, path = queue.popleft()
            if len(path) > max_depth:
                continue
            for edge_id in self._adj_out.get(current, set()):
                edge = self._edges.get(edge_id)
                if not edge or edge.target_node_id in visited:
                    continue
                next_node = self._nodes.get(edge.target_node_id)
                if not next_node:
                    continue
                new_path = path + [next_node]
                if edge.target_node_id == target_id:
                    return new_path
                visited.add(edge.target_node_id)
                queue.append((edge.target_node_id, new_path))

        return None

    # ── Orphan Detection ──

    def find_orphans(self) -> List[LineageNode]:
        """Find nodes with no incoming edges (except source types)."""
        orphans: List[LineageNode] = []
        for node_id, node in self._nodes.items():
            if node.node_type.is_source:
                continue
            if not self._adj_in.get(node_id):
                orphans.append(node)
        return orphans

    def find_broken_edges(self) -> List[LineageEdge]:
        """Find edges where source or target node is missing."""
        broken: List[LineageEdge] = []
        for edge in self._edges.values():
            if edge.source_node_id not in self._nodes:
                broken.append(edge)
            elif edge.target_node_id not in self._nodes:
                broken.append(edge)
        return broken

    # ── Properties ──

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    @property
    def is_empty(self) -> bool:
        return len(self._nodes) == 0

    # ── Internal ──

    def _traverse_upstream(
        self, node_id: str, visited: Set[str], result: List[LineageNode],
        depth: int, max_depth: int
    ) -> None:
        if depth >= max_depth or node_id in visited:
            return
        visited.add(node_id)
        for edge_id in self._adj_in.get(node_id, set()):
            edge = self._edges.get(edge_id)
            if not edge:
                continue
            parent = self._nodes.get(edge.source_node_id)
            if parent:
                result.append(parent)
                self._traverse_upstream(parent.node_id, visited, result, depth + 1, max_depth)

    def _traverse_downstream(
        self, node_id: str, visited: Set[str], result: List[LineageNode],
        depth: int, max_depth: int
    ) -> None:
        if depth >= max_depth or node_id in visited:
            return
        visited.add(node_id)
        for edge_id in self._adj_out.get(node_id, set()):
            edge = self._edges.get(edge_id)
            if not edge:
                continue
            child = self._nodes.get(edge.target_node_id)
            if child:
                result.append(child)
                self._traverse_downstream(child.node_id, visited, result, depth + 1, max_depth)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
            "node_count": self.node_count,
            "edge_count": self.edge_count,
        }
