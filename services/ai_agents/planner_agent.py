"""
ICYQuant Planner Agent — task decomposition and execution planning.

Breaks down high-level research/trading requests into structured,
executable task plans with dependencies, priorities, and
resource estimates.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PlanStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class PlanStepType(str, Enum):
    RESEARCH = "research"
    FACTOR = "factor"
    STRATEGY = "strategy"
    RISK = "risk"
    PORTFOLIO = "portfolio"
    VALIDATION = "validation"
    SYNTHESIS = "synthesis"
    DECISION = "decision"


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    step_type: PlanStepType = PlanStepType.RESEARCH
    description: str = ""
    assigned_agent_type: str = ""       # Type of agent to execute
    required_capabilities: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # step_ids
    estimated_duration_seconds: int = 60
    priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    """An execution plan with ordered steps."""
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    objective: str = ""
    status: PlanStatus = PlanStatus.DRAFT
    steps: list[PlanStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_estimated_duration: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class PlannerAgent:
    """Task decomposition and execution planning agent.

    Decomposes user requests into structured execution plans:
        1. Analyze the user's objective
        2. Identify required capabilities and data
        3. Sequence steps with dependency ordering
        4. Assign agent types to each step
        5. Estimate resource requirements
    """

    def __init__(self, agent_id: str = "planner_agent",
                 registry: Any = None) -> None:
        self.agent_id = agent_id
        self._registry = registry
        self._plans: dict[str, Plan] = {}
        self._total_plans = 0

    async def create_plan(self, objective: str,
                          context: Optional[dict[str, Any]] = None) -> Plan:
        """Create an execution plan for an objective."""
        self._total_plans += 1
        ctx = context or {}

        plan = Plan(objective=objective)
        self._plans[plan.plan_id] = plan

        # Phase 1: Research
        plan.steps.append(PlanStep(
            step_type=PlanStepType.RESEARCH,
            description=f"Research: {objective[:80]}",
            assigned_agent_type="researcher",
            required_capabilities=["market_analysis", "document_search"],
            priority=10,
            estimated_duration_seconds=120,
        ))

        # Phase 2: Factor Analysis (if quant-related)
        plan.steps.append(PlanStep(
            step_type=PlanStepType.FACTOR,
            description="Analyze relevant quantitative factors",
            assigned_agent_type="factor_agent",
            required_capabilities=["factor_generation", "factor_analysis"],
            dependencies=[plan.steps[0].step_id],
            priority=8,
            estimated_duration_seconds=180,
        ))

        # Phase 3: Strategy Building
        plan.steps.append(PlanStep(
            step_type=PlanStepType.STRATEGY,
            description="Build candidate strategies",
            assigned_agent_type="strategy_agent",
            required_capabilities=["strategy_generation", "backtest_request"],
            dependencies=[plan.steps[1].step_id],
            priority=8,
            estimated_duration_seconds=300,
        ))

        # Phase 4: Risk Assessment
        plan.steps.append(PlanStep(
            step_type=PlanStepType.RISK,
            description="Assess risk of candidate strategies",
            assigned_agent_type="risk_agent",
            required_capabilities=["risk_analysis", "stress_test"],
            dependencies=[plan.steps[2].step_id],
            priority=9,
            estimated_duration_seconds=180,
        ))

        # Phase 5: Portfolio
        plan.steps.append(PlanStep(
            step_type=PlanStepType.PORTFOLIO,
            description="Optimize portfolio allocation",
            assigned_agent_type="portfolio_agent",
            required_capabilities=["portfolio_optimization"],
            dependencies=[plan.steps[3].step_id],
            priority=7,
            estimated_duration_seconds=120,
        ))

        # Phase 6: Validation
        plan.steps.append(PlanStep(
            step_type=PlanStepType.VALIDATION,
            description="Review and validate outputs",
            assigned_agent_type="reviewer",
            required_capabilities=["quality_review"],
            dependencies=[plan.steps[4].step_id],
            priority=6,
            estimated_duration_seconds=90,
        ))

        plan.total_estimated_duration = sum(s.estimated_duration_seconds for s in plan.steps)
        plan.status = PlanStatus.READY

        logger.info("Plan %s created: %d steps, ~%ds estimated",
                     plan.plan_id, len(plan.steps), plan.total_estimated_duration)
        return plan

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        return self._plans.get(plan_id)

    def get_next_step(self, plan_id: str) -> Optional[PlanStep]:
        """Get the next executable step (all dependencies met)."""
        plan = self._plans.get(plan_id)
        if plan is None:
            return None

        completed = set()  # Would track completed steps
        for step in plan.steps:
            if all(dep in completed for dep in step.dependencies):
                return step
        return None

    @property
    def total_plans(self) -> int:
        return self._total_plans
