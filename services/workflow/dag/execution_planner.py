"""
Execution Planner — generates execution plans from the topological sort result.

Converts topological stages into an actionable execution plan with:
- Parallel groups (nodes that can execute concurrently)
- Execution stages (ordered groups)
- Resource estimates and scheduling hints
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from services.workflow.dag.dag import DAG, DAGNode
from services.workflow.dag.topological_sort import TopologicalSort, TopologicalResult

logger = logging.getLogger(__name__)


class ExecutionStrategy(str, Enum):
    """Execution strategies for the plan."""
    MAX_PARALLEL = "max_parallel"     # Maximize parallelism
    RESOURCE_AWARE = "resource_aware"  # Consider resource constraints
    PRIORITY_FIRST = "priority_first"  # Respect node priorities
    SEQUENTIAL = "sequential"         # Execute one stage at a time


@dataclass
class ExecutionStage:
    """A single stage in the execution plan."""

    stage_id: int
    nodes: List[str]
    estimated_duration_ms: float = 0.0
    resource_requirements: Dict[str, float] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    """Complete execution plan for a workflow."""

    workflow_id: str
    dag_id: str
    strategy: ExecutionStrategy = ExecutionStrategy.MAX_PARALLEL
    stages: List[ExecutionStage] = field(default_factory=list)
    total_nodes: int = 0
    total_stages: int = 0
    max_parallelism: int = 0
    estimated_total_duration_ms: float = 0.0
    critical_path: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExecutionPlanner:
    """
    Generates execution plans from compiled DAGs.

    Takes the topological sort result and produces a structured plan
    that the scheduler and executor can consume.
    """

    def __init__(self, topo_sort: Optional[TopologicalSort] = None):
        self.topo_sort = topo_sort or TopologicalSort()

    async def plan(
        self,
        dag: DAG,
        strategy: ExecutionStrategy = ExecutionStrategy.MAX_PARALLEL,
    ) -> ExecutionPlan:
        """
        Generate an execution plan for the DAG.

        Args:
            dag: The compiled DAG.
            strategy: Execution strategy to use.

        Returns:
            ExecutionPlan with stages and scheduling metadata.
        """
        topo_result = self.topo_sort.sort(dag)
        if not topo_result.is_valid:
            raise ValueError(f"Cannot plan invalid DAG: {topo_result.errors}")

        stages: List[ExecutionStage] = []
        for idx, stage_nodes in enumerate(topo_result.stages):
            stage = ExecutionStage(
                stage_id=idx,
                nodes=list(stage_nodes),
            )
            stages.append(stage)

        # Apply strategy-specific adjustments
        if strategy == ExecutionStrategy.RESOURCE_AWARE:
            stages = await self._apply_resource_constraints(stages, dag)
        elif strategy == ExecutionStrategy.PRIORITY_FIRST:
            stages = await self._apply_priority_ordering(stages, dag)
        elif strategy == ExecutionStrategy.SEQUENTIAL:
            stages = await self._flatten_to_sequential(stages)

        max_parallelism = max((len(s.nodes) for s in stages), default=0)

        return ExecutionPlan(
            workflow_id=dag.workflow_id,
            dag_id=dag.dag_id,
            strategy=strategy,
            stages=stages,
            total_nodes=dag.node_count,
            total_stages=len(stages),
            max_parallelism=max_parallelism,
            metadata={
                "topo_stages": len(topo_result.stages),
                "linear_order": topo_result.linear_order,
            },
        )

    async def _apply_resource_constraints(
        self, stages: List[ExecutionStage], dag: DAG
    ) -> List[ExecutionStage]:
        """Apply resource constraints — split stages if needed."""
        return stages

    async def _apply_priority_ordering(
        self, stages: List[ExecutionStage], dag: DAG
    ) -> List[ExecutionStage]:
        """Order nodes within each stage by priority."""
        for stage in stages:
            stage.nodes.sort(
                key=lambda nid: dag.nodes[nid].node.priority
                if dag.nodes[nid].node.priority is not None
                else 0,
                reverse=True,
            )
        return stages

    async def _flatten_to_sequential(
        self, stages: List[ExecutionStage]
    ) -> List[ExecutionStage]:
        """Flatten all stages into sequential single-node stages."""
        flattened = []
        stage_id = 0
        for stage in stages:
            for node_id in stage.nodes:
                flattened.append(ExecutionStage(stage_id=stage_id, nodes=[node_id]))
                stage_id += 1
        return flattened
