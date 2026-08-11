"""
ICYQuant Task Planner — decomposes research questions into actionable sub-tasks.

Breaks down complex research questions into structured, executable
sub-tasks with dependencies, priorities, and resource estimates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TaskPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


@dataclass
class ResearchTask:
    """A single research sub-task."""
    task_id: str
    description: str
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = field(default_factory=list)
    estimated_effort: str = "medium"
    assigned_tools: list[str] = field(default_factory=list)
    expected_output: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskPlan:
    """A complete research plan with ordered tasks."""
    plan_id: str
    question: str
    tasks: list[ResearchTask] = field(default_factory=list)
    estimated_total_effort: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskPlanner:
    """Decomposes research questions into structured task plans.

    Responsibilities:
        - Analyze research questions for decomposition
        - Generate ordered sub-tasks with dependencies
        - Assign priorities and tools to each task
        - Track task execution status
    """

    def __init__(self) -> None:
        self._plan_count = 0
        self._plans: dict[str, TaskPlan] = {}

    async def plan(
        self,
        question: str,
        context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Decompose a research question into an actionable task plan.

        Returns a list of task dictionaries for pipeline consumption.
        """
        self._plan_count += 1
        plan = self._decompose(question, context or {})

        # Store the plan
        self._plans[plan.plan_id] = plan

        # Convert to dict for pipeline
        return [
            {
                "task_id": t.task_id,
                "description": t.description,
                "priority": t.priority.value,
                "dependencies": t.dependencies,
                "estimated_effort": t.estimated_effort,
                "assigned_tools": t.assigned_tools,
                "expected_output": t.expected_output,
            }
            for t in plan.tasks
        ]

    def _decompose(self, question: str, context: dict[str, Any]) -> TaskPlan:
        """Analyze question and create a task plan.

        In production, this would use an LLM for intelligent decomposition.
        Here we use keyword-based heuristics.
        """
        import uuid

        plan_id = str(uuid.uuid4())
        question_lower = question.lower()
        tasks: list[ResearchTask] = []

        # Common research patterns
        has_analysis = any(kw in question_lower for kw in ["analyze", "analysis", "examine", "study"])
        has_compare = any(kw in question_lower for kw in ["compare", "versus", "vs", "difference"])
        has_predict = any(kw in question_lower for kw in ["predict", "forecast", "project", "estimate"])
        has_factor = any(kw in question_lower for kw in ["factor", "alpha", "signal", "indicator"])
        has_risk = any(kw in question_lower for kw in ["risk", "volatility", "drawdown", "exposure"])
        has_strategy = any(kw in question_lower for kw in ["strategy", "portfolio", "allocation", "weight"])

        task_idx = 0

        # Task 1: Literature / Knowledge Review
        tasks.append(ResearchTask(
            task_id=f"{plan_id}_t{task_idx}",
            description=f"Review existing knowledge about: {question[:100]}",
            priority=TaskPriority.HIGH,
            assigned_tools=["knowledge_search", "semantic_retrieval"],
            expected_output="Literature review summary",
        ))
        task_idx += 1

        # Task 2: Data Gathering
        tasks.append(ResearchTask(
            task_id=f"{plan_id}_t{task_idx}",
            description="Identify and gather relevant market data and datasets",
            priority=TaskPriority.HIGH,
            dependencies=[f"{plan_id}_t{task_idx - 1}"],
            assigned_tools=["data_catalog", "market_data_service"],
            expected_output="Dataset inventory",
        ))
        task_idx += 1

        # Task 3: Domain-specific analysis
        if has_factor:
            tasks.append(ResearchTask(
                task_id=f"{plan_id}_t{task_idx}",
                description="Construct and evaluate factor definitions",
                priority=TaskPriority.HIGH,
                dependencies=[f"{plan_id}_t{task_idx - 1}"],
                assigned_tools=["factor_analysis", "backtest_engine"],
                expected_output="Factor performance metrics",
            ))
            task_idx += 1

        if has_strategy:
            tasks.append(ResearchTask(
                task_id=f"{plan_id}_t{task_idx}",
                description="Design and backtest strategy based on findings",
                priority=TaskPriority.MEDIUM,
                dependencies=[f"{plan_id}_t{task_idx - 1}"],
                assigned_tools=["strategy_engine", "backtest_engine"],
                expected_output="Strategy backtest results",
            ))
            task_idx += 1

        if has_risk:
            tasks.append(ResearchTask(
                task_id=f"{plan_id}_t{task_idx}",
                description="Assess risk implications and exposure analysis",
                priority=TaskPriority.MEDIUM,
                dependencies=[f"{plan_id}_t{task_idx - 1}"],
                assigned_tools=["risk_analysis", "stress_test"],
                expected_output="Risk assessment report",
            ))
            task_idx += 1

        if has_compare:
            tasks.append(ResearchTask(
                task_id=f"{plan_id}_t{task_idx}",
                description="Perform comparative analysis",
                priority=TaskPriority.MEDIUM,
                dependencies=[f"{plan_id}_t{task_idx - 1}"],
                assigned_tools=["comparative_analysis"],
                expected_output="Comparison matrix",
            ))
            task_idx += 1

        if has_predict:
            tasks.append(ResearchTask(
                task_id=f"{plan_id}_t{task_idx}",
                description="Build and validate predictive model",
                priority=TaskPriority.MEDIUM,
                dependencies=[f"{plan_id}_t{task_idx - 1}"],
                assigned_tools=["ml_pipeline", "model_validation"],
                expected_output="Model performance report",
            ))
            task_idx += 1

        # Task N: Report generation
        tasks.append(ResearchTask(
            task_id=f"{plan_id}_t{task_idx}",
            description="Generate comprehensive research report with findings",
            priority=TaskPriority.HIGH,
            dependencies=[t.task_id for t in tasks],
            assigned_tools=["report_generator", "citation_manager"],
            expected_output="Final research report",
        ))
        task_idx += 1

        return TaskPlan(
            plan_id=plan_id,
            question=question,
            tasks=tasks,
            estimated_total_effort=self._estimate_effort(len(tasks)),
            metadata={"context": context},
        )

    @staticmethod
    def _estimate_effort(task_count: int) -> str:
        if task_count <= 3:
            return "low"
        elif task_count <= 6:
            return "medium"
        return "high"

    @property
    def plan_count(self) -> int:
        return self._plan_count
