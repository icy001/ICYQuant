"""
Topological Sort — orders DAG nodes by dependency using Kahn's algorithm.

Produces execution stages where all nodes in a stage can run in parallel.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from services.workflow.dag.dag import DAG

logger = logging.getLogger(__name__)


@dataclass
class TopologicalResult:
    """Result of topological sorting."""

    is_valid: bool
    stages: List[List[str]] = field(default_factory=list)
    linear_order: List[str] = field(default_factory=list)
    node_stage: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class TopologicalSort:
    """
    Topological sort using Kahn's algorithm (BFS-based).

    Groups nodes into execution stages:
    - Stage 0: source nodes (indegree == 0)
    - Stage 1: nodes whose dependencies are all in stage 0
    - Stage N: final sink nodes

    All nodes in the same stage can execute in parallel.
    """

    def __init__(self):
        pass

    def sort(self, dag: DAG) -> TopologicalResult:
        """
        Perform topological sort on the DAG.

        Returns TopologicalResult with execution stages.
        """
        errors: List[str] = []

        if dag.node_count == 0:
            errors.append("Cannot sort empty DAG")
            return TopologicalResult(is_valid=False, errors=errors)

        # Build indegree map
        indegree: Dict[str, int] = {}
        adjacency: Dict[str, List[str]] = {}

        for node_id in dag.nodes:
            indegree[node_id] = 0
            adjacency[node_id] = []

        for edge in dag.edges:
            if edge.source_id in indegree:
                adjacency[edge.source_id].append(edge.target_id)
            if edge.target_id in indegree:
                indegree[edge.target_id] += 1

        # Kahn's algorithm with stage grouping
        queue: deque = deque()
        for node_id, deg in indegree.items():
            if deg == 0:
                queue.append(node_id)

        stages: List[List[str]] = []
        linear_order: List[str] = []
        node_stage: Dict[str, int] = {}
        visited_count = 0

        while queue:
            stage_size = len(queue)
            current_stage: List[str] = []

            for _ in range(stage_size):
                node_id = queue.popleft()
                current_stage.append(node_id)
                linear_order.append(node_id)
                node_stage[node_id] = len(stages)
                visited_count += 1

                for successor in adjacency.get(node_id, []):
                    indegree[successor] -= 1
                    if indegree[successor] == 0:
                        queue.append(successor)

            stages.append(current_stage)

        # Check for remaining nodes (cycle or disconnected)
        if visited_count != dag.node_count:
            unprocessed = [nid for nid, deg in indegree.items() if deg > 0]
            errors.append(
                f"Topological sort incomplete: {visited_count}/{dag.node_count} nodes processed. "
                f"Unprocessed nodes: {unprocessed}. Possible cycle detected."
            )
            return TopologicalResult(is_valid=False, errors=errors)

        return TopologicalResult(
            is_valid=True,
            stages=stages,
            linear_order=linear_order,
            node_stage=node_stage,
        )

    def get_execution_order(self, dag: DAG) -> List[str]:
        """Get a flat execution order (linearized DAG)."""
        result = self.sort(dag)
        return result.linear_order

    def get_max_parallelism(self, dag: DAG) -> int:
        """Get the maximum number of nodes that can run in parallel."""
        result = self.sort(dag)
        if not result.stages:
            return 0
        return max(len(stage) for stage in result.stages)
