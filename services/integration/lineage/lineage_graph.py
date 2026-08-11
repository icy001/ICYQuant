"""Lineage Graph — the directed graph of nodes and edges for a lineage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .lineage_node import LineageNode, NodeType, NODE_TYPE_ORDER
from .lineage_edge import LineageEdge, EdgeType
from .lineage_errors import (
    LineageNodeNotFoundError,
    LineageEdgeNotFoundError,
    LineageCycleError,
    LineageBrokenLinkError,
)


@dataclass
class LineageGraph:
    """A complete directed graph capturing a single control lineage.

    Nodes = domain objects (Decision, Certificate, Order, etc.).
    Edges = semantic relationships between them.

    Supports forward and backward traversal, integrity checking,
    and serialization.
    """

    lineage_id: str = ""

    nodes: dict[str, LineageNode] = field(default_factory=dict)
    """node_id → LineageNode"""

    edges: list[LineageEdge] = field(default_factory=list)

    # ── Mutators ──────────────────────────────────────────────────

    def add_node(self, node: LineageNode) -> LineageNode:
        if node.lineage_id and self.lineage_id and node.lineage_id != self.lineage_id:
            node.lineage_id = self.lineage_id
        elif not node.lineage_id:
            node.lineage_id = self.lineage_id

        self.nodes[node.node_id] = node
        return node

    def add_edge(self, edge: LineageEdge) -> LineageEdge:
        if edge.from_node_id not in self.nodes:
            raise LineageNodeNotFoundError(
                edge.from_node_id, lineage_id=self.lineage_id,
            )
        if edge.to_node_id not in self.nodes:
            raise LineageNodeNotFoundError(
                edge.to_node_id, lineage_id=self.lineage_id,
            )
        if edge.lineage_id and self.lineage_id and edge.lineage_id != self.lineage_id:
            edge.lineage_id = self.lineage_id
        elif not edge.lineage_id:
            edge.lineage_id = self.lineage_id

        self.edges.append(edge)
        return edge

    # ── Queries ───────────────────────────────────────────────────

    def get_node(self, node_id: str) -> LineageNode:
        node = self.nodes.get(node_id)
        if node is None:
            raise LineageNodeNotFoundError(node_id, self.lineage_id)
        return node

    def get_nodes_by_type(self, node_type: NodeType) -> list[LineageNode]:
        return [n for n in self.nodes.values() if n.node_type == node_type]

    def get_node_by_object_id(self, object_id: str) -> LineageNode | None:
        for n in self.nodes.values():
            if n.object_id == object_id:
                return n
        return None

    # ── Adjacency ─────────────────────────────────────────────────

    def _adjacency(self) -> dict[str, list[tuple[str, EdgeType]]]:
        """from_node_id → [(to_node_id, edge_type), ...]"""
        adj: dict[str, list[tuple[str, EdgeType]]] = {
            nid: [] for nid in self.nodes
        }
        for e in self.edges:
            adj.setdefault(e.from_node_id, []).append(
                (e.to_node_id, e.edge_type),
            )
        return adj

    def _reverse_adjacency(self) -> dict[str, list[tuple[str, EdgeType]]]:
        """to_node_id → [(from_node_id, edge_type), ...]"""
        radj: dict[str, list[tuple[str, EdgeType]]] = {
            nid: [] for nid in self.nodes
        }
        for e in self.edges:
            radj.setdefault(e.to_node_id, []).append(
                (e.from_node_id, e.edge_type),
            )
        return radj

    # ── Traversal ─────────────────────────────────────────────────

    def forward_from(self, start_node_id: str) -> list[LineageNode]:
        """Return nodes reachable via forward traversal (BFS)."""
        adj = self._adjacency()
        visited: set[str] = set()
        result: list[LineageNode] = []
        queue: list[str] = [start_node_id]

        while queue:
            nid = queue.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            node = self.nodes.get(nid)
            if node:
                result.append(node)
            for to_id, _ in sorted(adj.get(nid, []),
                                   key=lambda x: NODE_TYPE_ORDER.get(
                                       self.nodes.get(x[0], LineageNode()).node_type,
                                       99,
                                   )):
                if to_id not in visited:
                    queue.append(to_id)

        return result

    def backward_from(self, start_node_id: str) -> list[LineageNode]:
        """Return ancestors via backward traversal (BFS up the graph)."""
        radj = self._reverse_adjacency()
        visited: set[str] = set()
        result: list[LineageNode] = []
        queue: list[str] = [start_node_id]

        while queue:
            nid = queue.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            node = self.nodes.get(nid)
            if node:
                result.insert(0, node)  # prepend — ancestors first
            for from_id, _ in radj.get(nid, []):
                if from_id not in visited:
                    queue.append(from_id)

        return result

    # ── Path finding ──────────────────────────────────────────────

    def find_path(self, from_node_id: str,
                  to_node_id: str) -> list[LineageNode]:
        """Find nodes on a path from from_node_id to to_node_id (BFS)."""
        adj = self._adjacency()
        visited: set[str] = {from_node_id}
        queue: list[tuple[str, list[str]]] = [(from_node_id, [from_node_id])]

        while queue:
            current, path = queue.pop(0)
            if current == to_node_id:
                return [self.nodes[nid] for nid in path]
            for next_id, _ in adj.get(current, []):
                if next_id not in visited:
                    visited.add(next_id)
                    queue.append((next_id, path + [next_id]))

        return []  # no path

    # ── Integrity ─────────────────────────────────────────────────

    def has_cycle(self) -> bool:
        """Return True if the graph contains a cycle (DFS)."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {nid: WHITE for nid in self.nodes}
        adj = self._adjacency()

        def _dfs(nid: str) -> bool:
            color[nid] = GRAY
            for next_id, _ in adj.get(nid, []):
                if color.get(next_id) == GRAY:
                    return True
                if color.get(next_id) == WHITE and _dfs(next_id):
                    return True
            color[nid] = BLACK
            return False

        for nid in self.nodes:
            if color.get(nid) == WHITE and _dfs(nid):
                return True
        return False

    def check_broken_links(self) -> list[str]:
        """Report nodes whose parent_node_id is set but no edge exists."""
        issues: list[str] = []
        radj = self._reverse_adjacency()
        for n in self.nodes.values():
            if n.parent_node_id and n.parent_node_id in self.nodes:
                to_nodes = {
                    from_id
                    for from_id, _ in radj.get(n.node_id, [])
                }
                if n.parent_node_id not in to_nodes:
                    issues.append(
                        f"Node {n.node_id} ({n.node_type.name}) "
                        f"references parent {n.parent_node_id} "
                        f"but no edge connects them"
                    )
        return issues

    # ── Properties ────────────────────────────────────────────────

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def root_nodes(self) -> list[str]:
        """Nodes with no incoming edges."""
        radj = self._reverse_adjacency()
        return [nid for nid in self.nodes
                if not radj.get(nid)]

    @property
    def leaf_nodes(self) -> list[str]:
        """Nodes with no outgoing edges."""
        adj = self._adjacency()
        return [nid for nid in self.nodes
                if not adj.get(nid)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "lineage_id": self.lineage_id,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
        }
