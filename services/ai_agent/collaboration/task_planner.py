"""Task Planner — goal decomposition engine that breaks user goals into executable subtask graphs.

Pipeline:
    PlanRequest (goal + context + constraints)
        -> TaskPlanner.analyze() (parse goal into domains)
        -> TaskPlanner.decompose() (break into subtasks)
        -> TaskPlanner.plan() (build TaskGraph with dependencies)
        -> PlanResult (task graph + agent assignments)

The Task Planner is used by the Coordinator Agent to convert natural language
goals into structured, executable task graphs with dependency ordering.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.collaboration.task_graph import (
    TaskGraph,
    TaskNode,
    TaskEdge,
    TaskNodeType,
)
from services.ai_agent.collaboration.dependency_graph import NodeStatus

logger = logging.getLogger(__name__)


class PlanStrategy(str, Enum):
    """Strategy for task decomposition."""
    DOMAIN_BASED = "domain_based"       # Decompose by business domain
    PIPELINE = "pipeline"               # Sequential pipeline steps
    PARALLEL = "parallel"               # Independent parallel tasks
    HIERARCHICAL = "hierarchical"       # Nested sub-goal decomposition


@dataclass
class PlanRequest:
    """A request to plan task decomposition for a goal.

    Attributes:
        goal: The user goal in natural language.
        context: Additional context for planning.
        strategy: Preferred decomposition strategy.
        max_depth: Maximum decomposition depth.
        constraints: Execution constraints (e.g. max parallelism).
    """

    goal: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    strategy: PlanStrategy = PlanStrategy.DOMAIN_BASED
    max_depth: int = 3
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanResult:
    """Result of task planning.

    Attributes:
        plan_id: Unique plan identifier.
        goal: The original goal.
        strategy: Strategy used for decomposition.
        task_graph: The resulting task graph.
        subtasks: List of subtask dictionaries for agent assignment.
        estimated_duration_seconds: Total estimated execution time.
    """

    plan_id: str = field(default_factory=lambda: uuid4().hex[:12])
    goal: str = ""
    strategy: PlanStrategy = PlanStrategy.DOMAIN_BASED
    task_graph: Optional[TaskGraph] = None
    subtasks: List[Dict[str, Any]] = field(default_factory=list)
    estimated_duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Return plan result as a dictionary."""
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "strategy": self.strategy.value,
            "subtask_count": len(self.subtasks),
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "subtasks": self.subtasks,
        }


class TaskPlanner:
    """Goal decomposition engine for multi-agent task planning.

    Converts natural language goals into structured task graphs with
    dependencies and agent capability requirements.

    Supports:
        - Domain-based decomposition (market, research, risk, etc.)
        - Pipeline (sequential) decomposition
        - Parallel (independent) decomposition
        - Hierarchical (nested) decomposition
        - Dependency inference between subtasks
        - Capability requirement assignment

    Usage:
        planner = TaskPlanner()
        await planner.initialize()
        request = PlanRequest(goal="Analyze market and generate report")
        result = await planner.plan(request)
    """

    # Domain definitions with their capabilities and typical subtasks
    DOMAINS = {
        "market": {
            "capabilities": ["market.analysis", "market.data"],
            "tasks": ["fetch_market_data", "analyze_market", "detect_signals"],
        },
        "research": {
            "capabilities": ["research.execute", "backtest.run"],
            "tasks": ["run_backtest", "analyze_results", "optimize_parameters"],
        },
        "risk": {
            "capabilities": ["risk.assessment", "risk.monitor"],
            "tasks": ["assess_risk", "check_limits", "stress_test"],
        },
        "strategy": {
            "capabilities": ["strategy.develop", "strategy.evaluate"],
            "tasks": ["develop_strategy", "evaluate_strategy", "generate_signals"],
        },
        "portfolio": {
            "capabilities": ["portfolio.manage", "portfolio.optimize"],
            "tasks": ["analyze_portfolio", "optimize_allocation", "rebalance"],
        },
        "execution": {
            "capabilities": ["execution.manage", "order.place"],
            "tasks": ["prepare_orders", "execute_orders", "confirm_fills"],
        },
        "reporting": {
            "capabilities": ["reporting.generate"],
            "tasks": ["gather_results", "format_report", "finalize_report"],
        },
    }

    def __init__(self) -> None:
        """Initialize the task planner."""
        self._initialized: bool = False
        logger.info("TaskPlanner created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the task planner."""
        if self._initialized:
            logger.warning("TaskPlanner already initialized")
            return
        self._initialized = True
        logger.info("TaskPlanner initialized")

    async def shutdown(self) -> None:
        """Shut down the task planner."""
        if not self._initialized:
            return
        self._initialized = False
        logger.info("TaskPlanner shutdown complete")

    # ── Planning ──

    async def plan(self, request: PlanRequest) -> PlanResult:
        """Plan task decomposition for a user goal.

        Args:
            request: The planning request.

        Returns:
            PlanResult with task graph and subtasks.
        """
        if not self._initialized:
            raise RuntimeError("TaskPlanner not initialized")

        logger.info("Planning for goal: %s (strategy=%s)", request.goal, request.strategy.value)

        if request.strategy == PlanStrategy.DOMAIN_BASED:
            return self._plan_domain_based(request)
        elif request.strategy == PlanStrategy.PIPELINE:
            return self._plan_pipeline(request)
        elif request.strategy == PlanStrategy.PARALLEL:
            return self._plan_parallel(request)
        else:
            return self._plan_domain_based(request)

    # ── Decomposition Strategies ──

    def _plan_domain_based(self, request: PlanRequest) -> PlanResult:
        """Decompose goal by matching business domains.

        Args:
            request: The planning request.

        Returns:
            PlanResult with domain-based task graph.
        """
        graph = TaskGraph()
        subtasks: List[Dict[str, Any]] = []
        goal_lower = request.goal.lower()

        matched_domains: List[str] = []
        domain_keywords = {
            "market": ["market", "price", "quote", "volatility", "trend"],
            "research": ["research", "backtest", "factor", "analyze", "study"],
            "risk": ["risk", "var", "exposure", "stress", "drawdown"],
            "strategy": ["strategy", "signal", "alpha", "trade idea"],
            "portfolio": ["portfolio", "allocation", "rebalance", "position"],
            "execution": ["execution", "order", "trade", "fill"],
            "reporting": ["report", "summary", "document"],
        }

        for domain, keywords in domain_keywords.items():
            if any(kw in goal_lower for kw in keywords):
                matched_domains.append(domain)

        # Always add reporting if other domains matched
        if matched_domains and "reporting" not in matched_domains:
            matched_domains.append("reporting")

        if not matched_domains:
            matched_domains = ["research", "reporting"]

        # Create task nodes for each domain
        prev_node_id: Optional[str] = None
        for domain in matched_domains:
            domain_def = self.DOMAINS.get(domain, {})
            main_task = domain_def.get("tasks", [f"{domain}_task"])[0]
            capabilities = domain_def.get("capabilities", [f"{domain}.execute"])

            node = TaskNode(
                node_id=uuid4().hex[:8],
                name=main_task,
                description=f"Execute {domain} analysis for: {request.goal}",
                node_type=TaskNodeType.ANALYSIS,
                required_capabilities=capabilities,
            )
            graph.add_node(node)

            subtasks.append({
                "id": node.node_id,
                "name": node.name,
                "description": node.description,
                "capabilities": capabilities,
                "domain": domain,
            })

            # Chain dependencies sequentially
            if prev_node_id:
                graph.add_edge(TaskEdge(from_node=prev_node_id, to_node=node.node_id))
            prev_node_id = node.node_id

        # Validate
        errors = graph.validate()
        if errors:
            logger.warning("Task graph validation warnings: %s", errors)

        # Estimate duration
        estimated = sum(
            n.estimated_duration_seconds for n in graph._nodes.values()
        )

        return PlanResult(
            goal=request.goal,
            strategy=PlanStrategy.DOMAIN_BASED,
            task_graph=graph,
            subtasks=subtasks,
            estimated_duration_seconds=estimated,
        )

    def _plan_pipeline(self, request: PlanRequest) -> PlanResult:
        """Decompose goal into a sequential pipeline.

        Args:
            request: The planning request.

        Returns:
            PlanResult with pipeline task graph.
        """
        graph = TaskGraph()
        subtasks: List[Dict[str, Any]] = []
        pipeline_steps = [
            ("data_collection", "Collect required data", ["data.access"]),
            ("analysis", "Analyze data", ["research.execute"]),
            ("evaluation", "Evaluate results", ["strategy.evaluate"]),
            ("recommendation", "Generate recommendations", ["reporting.generate"]),
        ]

        prev_id: Optional[str] = None
        for step_name, step_desc, capabilities in pipeline_steps:
            node = TaskNode(
                node_id=uuid4().hex[:8],
                name=step_name,
                description=f"{step_desc} for: {request.goal}",
                node_type=TaskNodeType.COMPUTATION,
                required_capabilities=capabilities,
            )
            graph.add_node(node)
            subtasks.append({
                "id": node.node_id,
                "name": node.name,
                "description": node.description,
                "capabilities": capabilities,
            })
            if prev_id:
                graph.add_edge(TaskEdge(from_node=prev_id, to_node=node.node_id))
            prev_id = node.node_id

        return PlanResult(
            goal=request.goal,
            strategy=PlanStrategy.PIPELINE,
            task_graph=graph,
            subtasks=subtasks,
            estimated_duration_seconds=40.0,
        )

    def _plan_parallel(self, request: PlanRequest) -> PlanResult:
        """Decompose goal into independent parallel tasks.

        Args:
            request: The planning request.

        Returns:
            PlanResult with parallel task graph (no edges).
        """
        graph = TaskGraph()
        subtasks: List[Dict[str, Any]] = []

        parallel_tasks = [
            ("market_analysis", "Analyze market conditions", ["market.analysis"]),
            ("risk_assessment", "Assess current risk", ["risk.assessment"]),
            ("portfolio_review", "Review portfolio state", ["portfolio.manage"]),
        ]

        task_ids: List[str] = []
        for name, desc, capabilities in parallel_tasks:
            node = TaskNode(
                node_id=uuid4().hex[:8],
                name=name,
                description=f"{desc} for: {request.goal}",
                node_type=TaskNodeType.ANALYSIS,
                required_capabilities=capabilities,
            )
            graph.add_node(node)
            subtasks.append({
                "id": node.node_id,
                "name": node.name,
                "description": node.description,
                "capabilities": capabilities,
            })
            task_ids.append(node.node_id)

        # Add aggregation node that depends on all parallel tasks
        agg_node = TaskNode(
            node_id=uuid4().hex[:8],
            name="aggregate_results",
            description=f"Aggregate results for: {request.goal}",
            node_type=TaskNodeType.AGGREGATION,
            required_capabilities=["reporting.generate"],
        )
        graph.add_node(agg_node)
        for tid in task_ids:
            graph.add_edge(TaskEdge(from_node=tid, to_node=agg_node.node_id))
        subtasks.append({
            "id": agg_node.node_id,
            "name": agg_node.name,
            "description": agg_node.description,
            "capabilities": ["reporting.generate"],
        })

        return PlanResult(
            goal=request.goal,
            strategy=PlanStrategy.PARALLEL,
            task_graph=graph,
            subtasks=subtasks,
            estimated_duration_seconds=20.0,
        )

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the task planner state.

        Returns:
            Dict with initialization status.
        """
        return {
            "initialized": self._initialized,
        }
