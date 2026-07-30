"""Feature Lineage — track data provenance and downstream impact.

Records the complete transformation chain from raw data to final
features, enabling impact analysis and debugging.

Usage::

    from services.feature_store import FeatureLineage, LineageNode

    lineage = FeatureLineage()
    lineage.add_node("raw_tick", type="source")
    lineage.add_node("bar_1min", type="transform")
    lineage.add_edge("raw_tick", "bar_1min")
    lineage.add_node("ema20", type="feature")
    lineage.add_edge("bar_1min", "ema20")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class NodeType(str, Enum):
    """Types of nodes in the lineage graph."""

    SOURCE = "source"          # Raw data source (tick, bar, etc.)
    TRANSFORM = "transform"    # Intermediate transformation
    FEATURE = "feature"        # Final feature
    FACTOR = "factor"          # Derived factor
    MODEL_INPUT = "model_input"  # Input to a model


@dataclass
class LineageNode:
    """A node in the feature lineage graph.

    Attributes:
        node_id: Unique node identifier.
        node_type: Type of node (source, transform, feature, etc.).
        description: Human-readable description.
        owner: Responsible team/individual.
        created_at: Unix timestamp.
        metadata: Arbitrary metadata.
    """

    node_id: str
    node_type: NodeType = NodeType.FEATURE
    description: str = ""
    owner: str = ""
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class LineageGraph:
    """A complete lineage graph snapshot.

    Attributes:
        nodes: All nodes in the graph.
        edges: Directed edges as (from_node, to_node) tuples.
        root_nodes: Nodes with no incoming edges.
    """

    nodes: Dict[str, LineageNode] = field(default_factory=dict)
    edges: Set[tuple[str, str]] = field(default_factory=set)
    root_nodes: List[str] = field(default_factory=list)


class FeatureLineage:
    """Manages feature lineage graphs.

    Tracks the provenance chain: source -> transform -> feature -> factor -> model_input.
    Supports upstream tracing (where does this come from?) and downstream
    impact analysis (what does this affect?).
    """

    # ---- 分组：初始化 ----

    def __init__(self) -> None:
        self._nodes: Dict[str, LineageNode] = {}
        # Adjacency lists for efficient traversal
        self._parents: Dict[str, Set[str]] = {}   # node -> set of parent nodes
        self._children: Dict[str, Set[str]] = {}  # node -> set of child nodes

    # ---- 分组：节点管理 ----

    def add_node(
        self,
        node_id: str,
        node_type: NodeType = NodeType.FEATURE,
        description: str = "",
        owner: str = "",
    ) -> LineageNode:
        """Add a node to the lineage graph.

        Args:
            node_id: Unique node identifier.
            node_type: Type of node.
            description: Human-readable description.
            owner: Responsible team.

        Returns:
            The created LineageNode.

        Raises:
            ValueError: If node already exists.
        """
        if node_id in self._nodes:
            raise ValueError(f"Node '{node_id}' already exists.")

        node = LineageNode(
            node_id=node_id,
            node_type=node_type,
            description=description,
            owner=owner,
        )
        self._nodes[node_id] = node
        self._parents.setdefault(node_id, set())
        self._children.setdefault(node_id, set())
        return node

    def get_node(self, node_id: str) -> LineageNode:
        """Get a lineage node.

        Args:
            node_id: Node identifier.

        Returns:
            The LineageNode.

        Raises:
            KeyError: If node not found.
        """
        if node_id not in self._nodes:
            raise KeyError(f"Node '{node_id}' not found.")
        return self._nodes[node_id]

    def remove_node(self, node_id: str) -> None:
        """Remove a node and all its edges.

        Args:
            node_id: Node identifier.

        Raises:
            KeyError: If node not found.
        """
        if node_id not in self._nodes:
            raise KeyError(f"Node '{node_id}' not found.")

        # Remove incoming edges
        for parent in list(self._parents.get(node_id, set())):
            self._children[parent].discard(node_id)
        # Remove outgoing edges
        for child in list(self._children.get(node_id, set())):
            self._parents[child].discard(node_id)

        del self._parents[node_id]
        del self._children[node_id]
        del self._nodes[node_id]

    # ---- 分组：边管理 ----

    def add_edge(self, from_node: str, to_node: str) -> None:
        """Add a directed edge between two nodes.

        Args:
            from_node: Upstream node.
            to_node: Downstream node.

        Raises:
            KeyError: If either node not found.
            ValueError: If edge would create a cycle.
        """
        if from_node not in self._nodes:
            raise KeyError(f"Node '{from_node}' not found.")
        if to_node not in self._nodes:
            raise KeyError(f"Node '{to_node}' not found.")

        if self._would_create_cycle(from_node, to_node):
            raise ValueError(
                f"Edge '{from_node}' -> '{to_node}' would create a cycle."
            )

        self._children[from_node].add(to_node)
        self._parents[to_node].add(from_node)

    def remove_edge(self, from_node: str, to_node: str) -> None:
        """Remove a directed edge.

        Args:
            from_node: Upstream node.
            to_node: Downstream node.
        """
        if from_node in self._children:
            self._children[from_node].discard(to_node)
        if to_node in self._parents:
            self._parents[to_node].discard(from_node)

    # ---- 分组：遍历 ----

    def get_upstream(self, node_id: str, max_depth: int = 10) -> List[str]:
        """Get all upstream (ancestor) nodes via BFS.

        Args:
            node_id: Starting node.
            max_depth: Maximum traversal depth.

        Returns:
            List of upstream node IDs in BFS order.

        Raises:
            KeyError: If node not found.
        """
        if node_id not in self._nodes:
            raise KeyError(f"Node '{node_id}' not found.")

        visited: Set[str] = set()
        result: List[str] = []
        queue: List[tuple[str, int]] = [(node_id, 0)]

        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for parent in self._parents.get(current, set()):
                if parent not in visited:
                    visited.add(parent)
                    result.append(parent)
                    queue.append((parent, depth + 1))

        return result

    def get_downstream(self, node_id: str, max_depth: int = 10) -> List[str]:
        """Get all downstream (descendant) nodes via BFS.

        Args:
            node_id: Starting node.
            max_depth: Maximum traversal depth.

        Returns:
            List of downstream node IDs in BFS order.

        Raises:
            KeyError: If node not found.
        """
        if node_id not in self._nodes:
            raise KeyError(f"Node '{node_id}' not found.")

        visited: Set[str] = set()
        result: List[str] = []
        queue: List[tuple[str, int]] = [(node_id, 0)]

        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for child in self._children.get(current, set()):
                if child not in visited:
                    visited.add(child)
                    result.append(child)
                    queue.append((child, depth + 1))

        return result

    def get_path(self, from_node: str, to_node: str) -> Optional[List[str]]:
        """Find a path from from_node to to_node using BFS.

        Args:
            from_node: Starting node.
            to_node: Target node.

        Returns:
            List of node IDs forming the path, or None if no path exists.

        Raises:
            KeyError: If either node not found.
        """
        if from_node not in self._nodes:
            raise KeyError(f"Node '{from_node}' not found.")
        if to_node not in self._nodes:
            raise KeyError(f"Node '{to_node}' not found.")

        if from_node == to_node:
            return [from_node]

        visited = {from_node}
        queue: List[tuple[str, List[str]]] = [(from_node, [from_node])]

        while queue:
            current, path = queue.pop(0)
            for child in self._children.get(current, set()):
                if child == to_node:
                    return path + [child]
                if child not in visited:
                    visited.add(child)
                    queue.append((child, path + [child]))

        return None

    # ---- 分组：图导出 ----

    def export_graph(self) -> LineageGraph:
        """Export the full lineage graph.

        Returns:
            LineageGraph with all nodes, edges, and root nodes.
        """
        all_edges: Set[tuple[str, str]] = set()
        for parent, children in self._children.items():
            for child in children:
                all_edges.add((parent, child))

        roots = [
            nid
            for nid in self._nodes
            if len(self._parents.get(nid, set())) == 0
        ]
        roots.sort()

        return LineageGraph(
            nodes=dict(self._nodes),
            edges=all_edges,
            root_nodes=roots,
        )

    def get_subgraph(self, node_id: str, direction: str = "both") -> LineageGraph:
        """Get a subgraph centered on a node.

        Args:
            node_id: Center node.
            direction: "upstream", "downstream", or "both".

        Returns:
            LineageGraph for the subgraph.

        Raises:
            KeyError: If node not found.
        """
        if node_id not in self._nodes:
            raise KeyError(f"Node '{node_id}' not found.")

        node_ids: Set[str] = {node_id}

        if direction in ("upstream", "both"):
            node_ids.update(self.get_upstream(node_id))

        if direction in ("downstream", "both"):
            node_ids.update(self.get_downstream(node_id))

        sub_nodes = {nid: self._nodes[nid] for nid in node_ids}
        sub_edges: Set[tuple[str, str]] = set()
        for parent in node_ids:
            for child in self._children.get(parent, set()):
                if child in node_ids:
                    sub_edges.add((parent, child))

        roots = [
            nid for nid in node_ids if len(self._parents.get(nid, set()) & node_ids) == 0
        ]
        roots.sort()

        return LineageGraph(nodes=sub_nodes, edges=sub_edges, root_nodes=roots)

    # ---- 分组：统计 ----

    def node_count(self) -> int:
        """Return total number of nodes."""
        return len(self._nodes)

    def edge_count(self) -> int:
        """Return total number of edges."""
        return sum(len(children) for children in self._children.values())

    # ---- 分组：内部 ----

    def _would_create_cycle(self, from_node: str, to_node: str) -> bool:
        """Check if adding edge (from_node -> to_node) would create a cycle."""
        # If to_node can already reach from_node, adding this edge creates a cycle
        visited: Set[str] = set()
        queue = [to_node]
        while queue:
            current = queue.pop(0)
            if current == from_node:
                return True
            if current in visited:
                continue
            visited.add(current)
            for child in self._children.get(current, set()):
                queue.append(child)
        return False
