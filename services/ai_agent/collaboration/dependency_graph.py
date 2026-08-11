"""Dependency Graph — DAG-based dependency tracking for agent tasks.

Pipeline:
    TaskNode (task with dependencies)
        -> DependencyGraph.add_node() (register node)
        -> DependencyGraph.add_edge() (define dependency: A must complete before B)
        -> DependencyGraph.resolve() (topological sort for execution order)
        -> DependencyGraph.ready_nodes() (nodes with all dependencies satisfied)
        -> DependencyGraph.mark_completed() / mark_failed() (update state)

Ensures tasks are executed in correct dependency order within the
multi-agent collaboration pipeline.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class NodeStatus(str, Enum):
    """Status of a dependency graph node."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


@dataclass
class DependencyNode:
    """A node in the dependency graph representing a task with prerequisites.

    Attributes:
        node_id: Unique node identifier.
        name: Human-readable node name.
        description: Task description.
        status: Current execution status.
        metadata: Additional node metadata.
        agent_id: Assigned agent ID.
        required_capabilities: Capabilities needed for this task.
    """

    node_id: str = ""
    name: str = ""
    description: str = ""
    status: NodeStatus = NodeStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    agent_id: str = ""
    required_capabilities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return node as a dictionary."""
        return {
            "node_id": self.node_id,
            "name": self.name,
            "status": self.status.value,
            "agent_id": self.agent_id,
            "capabilities": self.required_capabilities,
        }


@dataclass
class DependencyEdge:
    """A directed edge representing a dependency between two nodes.

    Attributes:
        from_node: The prerequisite node ID.
        to_node: The dependent node ID.
        condition: Optional condition that must be met.
    """

    from_node: str = ""
    to_node: str = ""
    condition: Optional[str] = None


class DependencyGraph:
    """DAG-based dependency tracker for agent task execution ordering.

    Builds and resolves directed acyclic graphs of task dependencies.
    Supports topological sorting for execution ordering, ready-node
    identification, and cycle detection.

    Supports:
        - Add/remove nodes and edges
        - Topological sort for execution order
        - Ready node identification (all deps satisfied)
        - Cycle detection
        - Status tracking per node
        - Dependency chain visualization
        - Cascading failure on parent failure

    Usage:
        graph = DependencyGraph()
        graph.add_node(DependencyNode(node_id="a", name="market_analysis"))
        graph.add_node(DependencyNode(node_id="b", name="risk_check"))
        graph.add_edge(DependencyEdge(from_node="a", to_node="b"))
        ready = graph.ready_nodes()  # ["a"]
        graph.mark_completed("a")
        ready = graph.ready_nodes()  # ["b"]
    """

    def __init__(self) -> None:
        """Initialize an empty dependency graph."""
        self._nodes: Dict[str, DependencyNode] = {}
        self._edges: List[DependencyEdge] = []
        self._incoming: Dict[str, Set[str]] = defaultdict(set)  # node_id -> {prerequisite_ids}
        self._outgoing: Dict[str, Set[str]] = defaultdict(set)  # node_id -> {dependent_ids}
        logger.info("DependencyGraph created")

    # ── Node Management ──

    def add_node(self, node: DependencyNode) -> None:
        """Add a node to the graph.

        Args:
            node: The dependency node to add.

        Raises:
            ValueError: If a node with the same ID already exists.
        """
        if node.node_id in self._nodes:
            raise ValueError(f"Node already exists: {node.node_id}")
        self._nodes[node.node_id] = node
        logger.debug("Dependency node added: %s", node.node_id)

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and its edges from the graph.

        Args:
            node_id: The node identifier.

        Returns:
            True if removed, False if not found.
        """
        if node_id not in self._nodes:
            return False

        del self._nodes[node_id]

        # Remove related edges
        self._edges = [
            e for e in self._edges
            if e.from_node != node_id and e.to_node != node_id
        ]
        self._incoming.pop(node_id, None)
        self._outgoing.pop(node_id, None)

        # Clean up references in other nodes
        for deps in self._incoming.values():
            deps.discard(node_id)
        for deps in self._outgoing.values():
            deps.discard(node_id)

        logger.debug("Dependency node removed: %s", node_id)
        return True

    # ── Edge Management ──

    def add_edge(self, edge: DependencyEdge) -> None:
        """Add a dependency edge between two nodes.

        Args:
            edge: The edge to add.

        Raises:
            ValueError: If either node doesn't exist.
        """
        if edge.from_node not in self._nodes:
            raise ValueError(f"Source node not found: {edge.from_node}")
        if edge.to_node not in self._nodes:
            raise ValueError(f"Target node not found: {edge.to_node}")

        self._edges.append(edge)
        self._outgoing[edge.from_node].add(edge.to_node)
        self._incoming[edge.to_node].add(edge.from_node)

        # Update status: target node is blocked until source completes
        target = self._nodes[edge.to_node]
        if target.status == NodeStatus.PENDING:
            target.status = NodeStatus.BLOCKED

        logger.debug("Dependency edge added: %s -> %s", edge.from_node, edge.to_node)

    # ── Resolution ──

    def ready_nodes(self) -> List[str]:
        """Return node IDs whose all dependencies are satisfied.

        Returns:
            List of ready node IDs in no particular order.
        """
        ready: List[str] = []
        for node_id, node in self._nodes.items():
            if node.status in (NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.SKIPPED):
                continue
            if node.status == NodeStatus.RUNNING:
                continue
            # Check all prerequisites are completed
            prereqs = self._incoming.get(node_id, set())
            if all(
                self._nodes[p].status == NodeStatus.COMPLETED
                for p in prereqs
                if p in self._nodes
            ):
                ready.append(node_id)
        return ready

    def topological_sort(self) -> List[str]:
        """Return nodes in topological order (Kahn's algorithm).

        Returns:
            Ordered list of node IDs. Empty if cycle detected.
        """
        in_degree: Dict[str, int] = {nid: 0 for nid in self._nodes}
        for edge in self._edges:
            if edge.to_node in in_degree:
                in_degree[edge.to_node] += 1

        queue: deque = deque(
            nid for nid, deg in in_degree.items() if deg == 0
        )
        result: List[str] = []

        while queue:
            node_id = queue.popleft()
            result.append(node_id)
            for dependent in self._outgoing.get(node_id, set()):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        if len(result) != len(self._nodes):
            logger.warning("Cycle detected in dependency graph")
            return []

        return result

    def has_cycle(self) -> bool:
        """Check whether the graph contains a cycle.

        Returns:
            True if a cycle is detected.
        """
        return len(self.topological_sort()) != len(self._nodes)

    # ── Status Management ──

    def mark_completed(self, node_id: str) -> None:
        """Mark a node as completed and update dependent nodes.

        Args:
            node_id: The node identifier.
        """
        node = self._nodes.get(node_id)
        if node:
            node.status = NodeStatus.COMPLETED
            logger.debug("Node completed: %s", node_id)

            # Unblock dependent nodes
            for dep_id in self._outgoing.get(node_id, set()):
                dep = self._nodes.get(dep_id)
                if dep and dep.status == NodeStatus.BLOCKED:
                    # Check if all prerequisites are now completed
                    prereqs = self._incoming.get(dep_id, set())
                    if all(
                        self._nodes[p].status == NodeStatus.COMPLETED
                        for p in prereqs
                        if p in self._nodes
                    ):
                        dep.status = NodeStatus.READY
                        logger.debug("Node unblocked: %s", dep_id)

    def mark_failed(self, node_id: str, cascade: bool = True) -> None:
        """Mark a node as failed. Optionally cascade failure to dependents.

        Args:
            node_id: The node identifier.
            cascade: Whether to mark dependents as failed too.
        """
        node = self._nodes.get(node_id)
        if node:
            node.status = NodeStatus.FAILED
            logger.debug("Node failed: %s", node_id)

            if cascade:
                for dep_id in self._outgoing.get(node_id, set()):
                    dep = self._nodes.get(dep_id)
                    if dep and dep.status not in (NodeStatus.COMPLETED, NodeStatus.FAILED):
                        self.mark_failed(dep_id, cascade=True)

    def mark_running(self, node_id: str) -> None:
        """Mark a node as currently running.

        Args:
            node_id: The node identifier.
        """
        node = self._nodes.get(node_id)
        if node:
            node.status = NodeStatus.RUNNING

    def mark_skipped(self, node_id: str) -> None:
        """Mark a node as skipped.

        Args:
            node_id: The node identifier.
        """
        node = self._nodes.get(node_id)
        if node:
            node.status = NodeStatus.SKIPPED

    # ── Query ──

    def get_node(self, node_id: str) -> Optional[DependencyNode]:
        """Get a node by ID.

        Args:
            node_id: The node identifier.

        Returns:
            The node, or None if not found.
        """
        return self._nodes.get(node_id)

    def get_dependencies(self, node_id: str) -> List[str]:
        """Get prerequisite node IDs for a given node.

        Args:
            node_id: The node identifier.

        Returns:
            List of prerequisite node IDs.
        """
        return list(self._incoming.get(node_id, set()))

    def get_dependents(self, node_id: str) -> List[str]:
        """Get dependent node IDs for a given node.

        Args:
            node_id: The node identifier.

        Returns:
            List of dependent node IDs.
        """
        return list(self._outgoing.get(node_id, set()))

    @property
    def node_count(self) -> int:
        """Return the number of nodes."""
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        """Return the number of edges."""
        return len(self._edges)

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the dependency graph state.

        Returns:
            Dict with node/edge counts and status breakdown.
        """
        status_counts: Dict[str, int] = {}
        for node in self._nodes.values():
            status_counts[node.status.value] = status_counts.get(node.status.value, 0) + 1

        return {
            "node_count": len(self._nodes),
            "edge_count": len(self._edges),
            "has_cycle": self.has_cycle(),
            "ready_nodes": len(self.ready_nodes()),
            "status_breakdown": status_counts,
        }
