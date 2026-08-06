"""
DAG Compiler — transforms a WorkflowDefinition into an optimized, validated, executable DAG.

Pipeline:
    WorkflowDefinition → Validate → Optimize → Build DAG → Topological Sort → Executable DAG
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from services.workflow.dag.dag import DAG, DAGStatus
from services.workflow.dag.dag_builder import DAGBuilder
from services.workflow.dag.dependency_graph import DependencyGraph
from services.workflow.dag.graph_validator import GraphValidator, ValidationResult
from services.workflow.dag.cycle_detector import CycleDetector
from services.workflow.dag.topological_sort import TopologicalSort, TopologicalResult
from services.workflow.dag.optimizer import ExecutionOptimizer
from services.workflow.models.workflow import WorkflowDefinition

logger = logging.getLogger(__name__)


@dataclass
class CompilationResult:
    """Result of DAG compilation."""

    success: bool
    dag: Optional[DAG] = None
    dependency_graph: Optional[DependencyGraph] = None
    topological_result: Optional[TopologicalResult] = None
    validation_result: Optional[ValidationResult] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DAGCompiler:
    """
    Compiles a WorkflowDefinition into an executable DAG.

    Phases:
    1. Validation — structural checks, cycle detection
    2. Graph construction — build dependency graph
    3. Optimization — merge stages, parallelize
    4. Topological sort — determine execution order
    5. DAG assembly — final executable DAG
    """

    def __init__(
        self,
        validator: Optional[GraphValidator] = None,
        cycle_detector: Optional[CycleDetector] = None,
        topo_sort: Optional[TopologicalSort] = None,
        optimizer: Optional[ExecutionOptimizer] = None,
    ):
        self.validator = validator or GraphValidator()
        self.cycle_detector = cycle_detector or CycleDetector()
        self.topo_sort = topo_sort or TopologicalSort()
        self.optimizer = optimizer or ExecutionOptimizer()

    async def compile(self, workflow: WorkflowDefinition) -> CompilationResult:
        """
        Full compilation pipeline.

        Returns CompilationResult with success flag and compiled DAG or errors.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Phase 1: Build DAG
        builder = DAGBuilder()
        builder.from_workflow(workflow)
        dag = builder.build()
        dep_graph = builder.to_dependency_graph()

        # Phase 2: Validate
        validation = await self.validator.validate(dag, dep_graph)
        if not validation.is_valid:
            errors.extend(validation.errors)
            return CompilationResult(
                success=False,
                validation_result=validation,
                errors=errors,
                warnings=validation.warnings,
            )
        warnings.extend(validation.warnings)

        # Phase 3: Cycle detection
        has_cycle, cycle_nodes = self.cycle_detector.detect(dag)
        if has_cycle:
            errors.append(f"Cycle detected in DAG: {' -> '.join(cycle_nodes)}")
            return CompilationResult(
                success=False, dag=dag, errors=errors, warnings=warnings
            )

        # Phase 4: Optimize
        dag = await self.optimizer.optimize(dag)

        # Phase 5: Topological sort
        topo_result = self.topo_sort.sort(dag)
        if not topo_result.is_valid:
            errors.extend(topo_result.errors)
            return CompilationResult(
                success=False, dag=dag, topological_result=topo_result,
                errors=errors, warnings=warnings,
            )

        # Assign stages to DAG
        dag.stages = topo_result.stages
        for stage_idx, stage_nodes in enumerate(topo_result.stages):
            for node_id in stage_nodes:
                if node_id in dag.nodes:
                    dag.nodes[node_id].stage = stage_idx

        dag.status = DAGStatus.VALIDATED
        return CompilationResult(
            success=True,
            dag=dag,
            dependency_graph=dep_graph,
            topological_result=topo_result,
            validation_result=validation,
            warnings=warnings,
            metadata={
                "stages": len(topo_result.stages),
                "max_parallelism": max((len(s) for s in topo_result.stages), default=0),
                "node_count": dag.node_count,
                "edge_count": dag.edge_count,
            },
        )

    async def quick_validate(self, workflow: WorkflowDefinition) -> ValidationResult:
        """Quick validation without full compilation."""
        builder = DAGBuilder()
        builder.from_workflow(workflow)
        dag = builder.build()
        dep_graph = builder.to_dependency_graph()
        return await self.validator.validate(dag, dep_graph)
