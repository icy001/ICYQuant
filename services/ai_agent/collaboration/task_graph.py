"""Task Graph — DAG-based task decomposition and execution tracking.

Pipeline:
    User Goal
        -> TaskGraph.create_from_goal() (decompose goal into task nodes)
        -> TaskGraph.add_edge() (define task dependencies)
        -> TaskGraph.validate() (check DAG integrity)
        -> TaskGraph.execute() (topological execution order)
        -> TaskGraph.get_progress() (track completion)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.collaboration.dependency_graph import (
    DependencyGraph,
    DependencyNode,
    DependencyEdge,
    NodeStatus,
)

logger = logging.getLogger(__name__)


class TaskNodeType(str, Enum):
    """Types of task nodes."""
    ANALYSIS = "analysis"
    COMPUTATION = "computation"
    DECISION = "decision"
    ACTION = "action"
    VALIDATION = "validation"
    AGGREGATION = "aggregation"


@dataclass
class TaskNode:
    """A node in the task graph representing a unit of work.

    Attributes:
        node_id: Unique node identifier.
        name: Human-readable task name.
        description: Detailed task description.
        node_type: Type of task.
        required_capabilities: Capabilities needed for this task.
        assigned_agent_id: Agent assigned to execute this task.
        status: Current execution status.
        result: Execution result (set after completion).
        priority: Task priority (higher = more important).
        estimated_duration_seconds: Estimated execution time.
        metadata: Additional task metadata.
    """

    node_id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    description: str = ""
    node_type: TaskNodeType = TaskNodeType.COMPUTATION
    required_capabilities: List[str] = field(default_factory=list)
    assigned_agent_id: str = ""
    status: NodeStatus = NodeStatus.PENDING
    result: Any = None
    priority: int = 0
    estimated_duration_seconds: float = 10.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return task node as a dictionary."""
        return {
            "node_id": self.node_id,
            "name": self.name,
            "description": self.description,
            "node_type": self.node_type.value,
            "required_capabilities": self.required_capabilities,
            "assigned_agent_id": self.assigned_agent_id,
            "status": self.status.value,
            "priority": self.priority,
        }


@dataclass
class TaskEdge:
    """A directed edge in the task graph representing execution dependency.

    Attributes:
        from_node: The prerequisite task node ID.
        to_node: The dependent task node ID.
        data_flow: Whether data flows from source to target.
    """

    from_node: str = ""
    to_node: str = ""
    data_flow: bool = True


class TaskGraph:
    """DAG-based task decomposition and execution tracking.

    Decomposes user goals into a directed acyclic graph of tasks, tracking
    dependencies and execution progress.

    Supports:
        - Task node and edge management
        - DAG validation (cycle detection)
        - Topological execution ordering
        - Progress tracking
        - Task-to-agent assignment
        - Data flow between tasks

    Usage:
        graph = TaskGraph()
        graph.add_node(TaskNode(name="market_analysis", ...))
        graph.add_node(TaskNode(name="risk_check", ...))
        graph.add_edge(TaskEdge(from_node="a", to_node="b"))
        order = graph.execution_order()
    """

    def __init__(self) -> None:
        """Initialize an empty task graph."""
        self._dep_graph: DependencyGraph = DependencyGraph()
        self._nodes: Dict[str, TaskNode] = {}
        self._edges: List[TaskEdge] = []
        self._graph_id: str = uuid4().hex[:8]
        logger.info("TaskGraph created [%s]", self._graph_id)

    # ── Node Management ──

    def add_node(self, node: TaskNode) -> None:
        """Add a task node to the graph.

        Args:
            node: The task node to add.

        Raises:
            ValueError: If a node with the same ID already exists.
        """
        if node.node_id in self._nodes:
            raise ValueError(f"Task node already exists: {node.node_id}")

        self._nodes[node.node_id] = node
        self._dep_graph.add_node(DependencyNode(
            node_id=node.node_id,
            name=node.name,
            description=node.description,
            required_capabilities=node.required_capabilities,
            agent_id=node.assigned_agent_id,
            metadata=node.metadata,
        ))
        logger.debug("Task node added: %s (%s)", node.node_id, node.name)

    def remove_node(self, node_id: str) -> bool:
        """Remove a task node and its edges.

        Args:
            node_id: The node identifier.

        Returns:
            True if removed.
        """
        if node_id not in self._nodes:
            return False
        del self._nodes[node_id]
        self._dep_graph.remove_node(node_id)
        self._edges = [
            e for e in self._edges
            if e.from_node != node_id and e.to_node != node_id
        ]
        logger.debug("Task node removed: %s", node_id)
        return True

    # ── Edge Management ──

    def add_edge(self, edge: TaskEdge) -> None:
        """Add a dependency edge between two task nodes.

        Args:
            edge: The edge to add.
        """
        self._edges.append(edge)
        self._dep_graph.add_edge(DependencyEdge(
            from_node=edge.from_node,
            to_node=edge.to_node,
        ))
        logger.debug("Task edge added: %s -> %s", edge.from_node, edge.to_node)

    # ── Execution ──

    def execution_order(self) -> List[str]:
        """Return task node IDs in topological execution order.

        Returns:
            Ordered list of node IDs. Empty if cycle detected.
        """
        return self._dep_graph.topological_sort()

    def ready_nodes(self) -> List[TaskNode]:
        """Return task nodes whose all dependencies are satisfied.

        Returns:
            List of ready task nodes.
        """
        ready_ids = self._dep_graph.ready_nodes()
        return [self._nodes[nid] for nid in ready_ids if nid in self._nodes]

    # ── Validation ──

    def validate(self) -> List[str]:
        """Validate the task graph for structural issues.

        Returns:
            List of validation error messages. Empty if valid.
        """
        errors: List[str] = []

        # Check for cycles
        if self._dep_graph.has_cycle():
            errors.append("Task graph contains a cycle")

        # Check for disconnected nodes
        connected: set = set()
        for edge in self._edges:
            connected.add(edge.from_node)
            connected.add(edge.to_node)
        disconnected = set(self._nodes.keys()) - connected
        for nid in disconnected:
            errors.append(f"Task node '{nid}' has no dependencies")

        # Check all edge references exist
        for edge in self._edges:
            if edge.from_node not in self._nodes:
                errors.append(f"Edge references non-existent from_node: {edge.from_node}")
            if edge.to_node not in self._nodes:
                errors.append(f"Edge references non-existent to_node: {edge.to_node}")

        return errors

    # ── Progress ──

    def get_progress(self) -> Dict[str, Any]:
        """Return execution progress of the task graph.

        Returns:
            Dict with completion percentages and status breakdown.
        """
        total = len(self._nodes)
        if total == 0:
            return {"total": 0, "completed": 0, "percentage": 0.0}

        status_counts: Dict[str, int] = {}
        for node in self._nodes.values():
            status_counts[node.status.value] = status_counts.get(node.status.value, 0) + 1

        completed = status_counts.get("completed", 0)
        return {
            "total": total,
            "completed": completed,
            "failed": status_counts.get("failed", 0),
            "running": status_counts.get("running", 0),
            "pending": status_counts.get("pending", 0) + status_counts.get("blocked", 0),
            "percentage": round(completed / total * 100, 1),
            "ready": len(self.ready_nodes()),
        }

    # ── Node Update ──

    def mark_completed(self, node_id: str, result: Any = None) -> None:
        """Mark a task node as completed.

        Args:
            node_id: The node identifier.
            result: Optional execution result.
        """
        node = self._nodes.get(node_id)
        if node:
            node.status = NodeStatus.COMPLETED
            node.result = result
        self._dep_graph.mark_completed(node_id)

    def mark_failed(self, node_id: str, cascade: bool = True) -> None:
        """Mark a task node as failed.

        Args:
            node_id: The node identifier.
            cascade: Whether to cascade failure to dependents.
        """
        node = self._nodes.get(node_id)
        if node:
            node.status = NodeStatus.FAILED
        self._dep_graph.mark_failed(node_id, cascade=cascade)

    def assign_agent(self, node_id: str, agent_id: str) -> None:
        """Assign an agent to a task node.

        Args:
            node_id: The task node ID.
            agent_id: The agent ID.
        """
        node = self._nodes.get(node_id)
        if node:
            node.assigned_agent_id = agent_id
            dep_node = self._dep_graph.get_node(node_id)
            if dep_node:
                dep_node.agent_id = agent_id

    # ── Properties ──

    @property
    def node_count(self) -> int:
        """Return the number of task nodes."""
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        """Return the number of task edges."""
        return len(self._edges)

    @property
    def graph_id(self) -> str:
        """Return the graph ID."""
        return self._graph_id

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the task graph state.

        Returns:
            Dict with graph metadata and progress.
        """
        return {
            "graph_id": self._graph_id,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "progress": self.get_progress(),
            "validation_errors": self.validate(),
        }
