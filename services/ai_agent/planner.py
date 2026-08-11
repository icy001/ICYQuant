"""
Goal-oriented planning engine.

Decomposes high-level goals into structured execution plans
with task graphs, dependency analysis, and dynamic replanning.

Pipeline:
    Goal → Task Decomposition → Execution Plan → Workflow
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ── Plan Types ──


class PlanStatus(str, Enum):
    """Execution plan status."""

    DRAFT = "draft"
    VALIDATED = "validated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepType(str, Enum):
    """Types of plan steps."""

    THINK = "think"           # Analyze and reason
    ACT = "act"               # Execute action
    OBSERVE = "observe"       # Observe result
    DECIDE = "decide"         # Make decision
    VERIFY = "verify"         # Verify outcome
    PARALLEL = "parallel"     # Parallel execution group
    CONDITIONAL = "conditional"  # Conditional branch


class StepDependency(str, Enum):
    """Step dependency types."""

    REQUIRED = "required"     # Must complete before this step
    OPTIONAL = "optional"     # Nice to have completed
    CONFLICT = "conflict"     # Cannot run together


@dataclass
class PlanStep:
    """A single step in an execution plan."""

    step_id: str = field(default_factory=lambda: uuid4().hex)
    name: str = ""
    description: str = ""
    step_type: StepType = StepType.ACT
    priority: int = 0
    estimated_duration_seconds: float = 0.0
    dependencies: List[str] = field(default_factory=list)
    dependency_type: StepDependency = StepDependency.REQUIRED
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_output: Optional[str] = None
    retry_policy: Optional[Dict[str, Any]] = None
    timeout_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary."""
        return {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "step_type": self.step_type.value,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "parameters_keys": list(self.parameters.keys()),
            "estimated_duration": self.estimated_duration_seconds,
        }


@dataclass
class Plan:
    """Structured execution plan composed of ordered steps.

    Represents the decomposed result of a goal.
    """

    plan_id: str = field(default_factory=lambda: uuid4().hex)
    goal: str = ""
    session_id: str = ""
    status: PlanStatus = PlanStatus.DRAFT
    steps: List[PlanStep] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    total_estimated_seconds: float = 0.0
    created_at: Optional[str] = None
    version: int = 1

    @property
    def step_count(self) -> int:
        """Total number of steps."""
        return len(self.steps)

    @property
    def critical_path(self) -> List[str]:
        """Get steps on the critical path (longest dependency chain)."""
        # Simple heuristic: steps with most dependencies
        dep_count = {s.step_id: len(s.dependencies) for s in self.steps}
        return sorted(dep_count, key=dep_count.get, reverse=True)[:5]

    def add_step(self, step: PlanStep) -> "Plan":
        """Add a step to the plan."""
        self.steps.append(step)
        self.total_estimated_seconds += step.estimated_duration_seconds
        return self

    def get_step(self, step_id: str) -> Optional[PlanStep]:
        """Get a step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_ready_steps(self, completed_step_ids: List[str]) -> List[PlanStep]:
        """Get steps whose dependencies are all satisfied."""
        ready = []
        for step in self.steps:
            if step.step_id in completed_step_ids:
                continue
            if all(dep in completed_step_ids for dep in step.dependencies):
                ready.append(step)
        return ready

    def validate(self) -> List[str]:
        """Validate plan structure. Returns list of issues."""
        issues = []
        step_ids = {s.step_id for s in self.steps}

        for step in self.steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    issues.append(f"Step [{step.step_id}] references unknown dependency: {dep}")

        # Check for cycles (simple check)
        for step in self.steps:
            if step.step_id in step.dependencies:
                issues.append(f"Step [{step.step_id}] depends on itself")

        if not self.steps:
            issues.append("Plan has no steps")

        if not issues:
            self.status = PlanStatus.VALIDATED

        return issues

    def to_summary(self) -> Dict[str, Any]:
        """Generate plan summary."""
        return {
            "plan_id": self.plan_id,
            "goal": self.goal[:100],
            "status": self.status.value,
            "step_count": self.step_count,
            "total_estimated_seconds": self.total_estimated_seconds,
            "critical_path": self.critical_path,
            "steps": [s.to_dict() for s in self.steps],
        }


# ── Planner ──


class Planner:
    """Goal-oriented planning engine.

    Decomposes high-level goals into structured execution plans.

    Supports:
        - Goal decomposition into tasks
        - Task dependency graph construction
        - Plan validation and optimization
        - Dynamic replanning based on execution feedback

    Usage:
        planner = Planner()
        plan = planner.plan(
            goal="Analyze recent market trends for BTC/USDT",
            context={"timeframe": "1d"},
        )
    """

    def __init__(self) -> None:
        self._plan_count: int = 0
        logger.info("Planner initialized")

    # ── Planning ──

    def plan(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        session_id: str = "",
    ) -> Plan:
        """Create an execution plan from a goal.

        Decomposes the goal into a sequence of executable steps
        with dependency relationships.

        Args:
            goal: High-level goal description.
            context: Additional context for planning.
            constraints: Constraints that must be satisfied.
            session_id: Associated session identifier.

        Returns:
            Structured Plan with ordered steps.
        """
        self._plan_count += 1
        logger.info(f"Planning goal [{self._plan_count}]: {goal[:80]}")

        plan = Plan(
            goal=goal,
            session_id=session_id,
            context=context or {},
            constraints=constraints or {},
        )

        # Decompose goal into steps
        steps = self._decompose_goal(goal, context, constraints)
        for step in steps:
            plan.add_step(step)

        # Validate plan structure
        issues = plan.validate()
        if issues:
            logger.warning(f"Plan validation issues: {issues}")

        logger.info(
            f"Plan created: {plan.plan_id}",
            extra={"steps": plan.step_count, "issues": len(issues)},
        )

        return plan

    def _decompose_goal(
        self,
        goal: str,
        context: Optional[Dict[str, Any]],
        constraints: Optional[Dict[str, Any]],
    ) -> List[PlanStep]:
        """Decompose a goal into plan steps.

        TODO: In future versions, this will use LLM-based decomposition.
        Currently uses a rule-based heuristic approach.
        """
        steps: List[PlanStep] = []

        # Phase 1: Understand the goal
        think_step = PlanStep(
            name="Analyze Goal",
            description=f"Parse and understand the objective: {goal}",
            step_type=StepType.THINK,
            priority=10,
            estimated_duration_seconds=1.0,
        )
        steps.append(think_step)

        # Phase 2: Gather context
        gather_step = PlanStep(
            name="Gather Context",
            description="Retrieve relevant context and data for the task",
            step_type=StepType.OBSERVE,
            priority=9,
            dependencies=[think_step.step_id],
            estimated_duration_seconds=2.0,
        )
        steps.append(gather_step)

        # Phase 3: Execute core task
        exec_step = PlanStep(
            name="Execute Task",
            description=f"Execute the primary task: {goal}",
            step_type=StepType.ACT,
            priority=8,
            dependencies=[gather_step.step_id],
            estimated_duration_seconds=5.0,
            parameters={"context": context or {}, "constraints": constraints or {}},
        )
        steps.append(exec_step)

        # Phase 4: Verify result
        verify_step = PlanStep(
            name="Verify Result",
            description="Validate execution output meets requirements",
            step_type=StepType.VERIFY,
            priority=7,
            dependencies=[exec_step.step_id],
            estimated_duration_seconds=1.0,
        )
        steps.append(verify_step)

        return steps

    # ── Replanning ──

    def replan(
        self,
        original_plan: Plan,
        feedback: Dict[str, Any],
    ) -> Plan:
        """Create an updated plan based on execution feedback.

        Args:
            original_plan: The plan that needs revision.
            feedback: Feedback from execution (errors, observations).

        Returns:
            Updated Plan with new version.
        """
        logger.info(f"Replanning: {original_plan.plan_id}")

        new_plan = Plan(
            goal=original_plan.goal,
            session_id=original_plan.session_id,
            context={**original_plan.context, "feedback": feedback},
            constraints=original_plan.constraints,
            version=original_plan.version + 1,
        )

        # Keep completed steps, add new corrective steps
        completed_ids = feedback.get("completed_steps", [])
        for step in original_plan.steps:
            if step.step_id in completed_ids:
                new_plan.add_step(step)

        # Add corrective action
        correction_step = PlanStep(
            name="Apply Correction",
            description=f"Adjust plan based on: {feedback.get('error', 'feedback')}",
            step_type=StepType.ACT,
            dependencies=completed_ids,
        )
        new_plan.add_step(correction_step)

        return new_plan

    # ── Status ──

    def get_status(self) -> Dict[str, Any]:
        """Get planner status."""
        return {
            "total_plans_created": self._plan_count,
        }
