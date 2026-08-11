"""
Unified reasoning engine.

Supports multiple reasoning modes:
    Rule Based → Chain Reasoning → Reflection → Decision

Designed for future LLM integration with pluggable reasoning strategies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from services.ai_agent.planner import Plan, PlanStep

logger = logging.getLogger(__name__)


# ── Reasoning Types ──


class ReasoningMode(str, Enum):
    """Available reasoning strategies."""

    RULE_BASED = "rule_based"       # Deterministic rule application
    CHAIN = "chain"                 # Sequential step reasoning
    REFLECTION = "reflection"       # Self-reflection and critique
    TREE = "tree"                   # Tree-of-thought exploration
    VOTING = "voting"               # Multi-path consensus
    LLM = "llm"                     # LLM-powered reasoning (future)


class DecisionType(str, Enum):
    """Types of reasoning decisions."""

    PROCEED = "proceed"             # Continue with current plan
    MODIFY = "modify"               # Modify the plan
    RETRY = "retry"                 # Retry current step
    ABORT = "abort"                 # Stop execution
    ESCALATE = "escalate"           # Escalate to human/supervisor
    WAIT = "wait"                   # Wait for condition


@dataclass
class ReasoningStep:
    """A single step in the reasoning chain."""

    step_id: str = field(default_factory=lambda: uuid4().hex)
    mode: ReasoningMode = ReasoningMode.RULE_BASED
    input: Any = None
    output: Any = None
    confidence: float = 1.0
    explanation: str = ""
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningResult:
    """Complete reasoning result with chain and decision."""

    result_id: str = field(default_factory=lambda: uuid4().hex)
    session_id: str = ""
    plan_id: str = ""
    chain: List[ReasoningStep] = field(default_factory=list)
    decision: DecisionType = DecisionType.PROCEED
    decision_rationale: str = ""
    confidence: float = 0.0
    suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def step_count(self) -> int:
        """Number of reasoning steps."""
        return len(self.chain)

    def add_step(self, step: ReasoningStep) -> None:
        """Add a reasoning step to the chain."""
        self.chain.append(step)

    def to_summary(self) -> Dict[str, Any]:
        """Generate reasoning result summary."""
        return {
            "result_id": self.result_id,
            "plan_id": self.plan_id,
            "decision": self.decision.value,
            "confidence": self.confidence,
            "steps": [
                {
                    "mode": s.mode.value,
                    "confidence": s.confidence,
                    "explanation": s.explanation[:100],
                }
                for s in self.chain
            ],
            "suggestions": self.suggestions,
        }


# ── Reasoning Engine ──


class ReasoningEngine:
    """Unified reasoning engine with multiple reasoning modes.

    Analyzes plans, applies reasoning strategies, and produces
    decisions that guide execution.

    Supports:
        - Rule-based reasoning for deterministic decisions
        - Chain reasoning for sequential analysis
        - Reflection for self-critique and improvement
        - Extensible architecture for future LLM integration

    Usage:
        engine = ReasoningEngine()
        result = engine.reason(plan=plan, context={})
    """

    def __init__(self) -> None:
        self._result_count: int = 0
        self._strategy_registry: Dict[ReasoningMode, Optional[Callable]] = {
            ReasoningMode.RULE_BASED: None,  # Built-in
            ReasoningMode.CHAIN: None,        # Built-in
            ReasoningMode.REFLECTION: None,   # Built-in
        }
        logger.info("ReasoningEngine initialized")

    # ── Main Reasoning ──

    def reason(
        self,
        plan: Plan,
        context: Optional[Dict[str, Any]] = None,
        session_id: str = "",
        mode: ReasoningMode = ReasoningMode.CHAIN,
    ) -> ReasoningResult:
        """Perform reasoning on a plan.

        Args:
            plan: The execution plan to reason about.
            context: Additional context for reasoning.
            session_id: Associated session.
            mode: Reasoning strategy to use.

        Returns:
            ReasoningResult with chain and decision.
        """
        self._result_count += 1
        logger.info(
            f"Reasoning [{self._result_count}] on plan {plan.plan_id}",
            extra={"mode": mode.value, "steps": plan.step_count},
        )

        result = ReasoningResult(
            session_id=session_id,
            plan_id=plan.plan_id,
        )

        # Select and apply reasoning strategy
        if mode == ReasoningMode.RULE_BASED:
            result = self._rule_based_reason(plan, context, result)
        elif mode == ReasoningMode.CHAIN:
            result = self._chain_reason(plan, context, result)
        elif mode == ReasoningMode.REFLECTION:
            result = self._reflection_reason(plan, context, result)
        else:
            logger.warning(f"Unknown reasoning mode: {mode}, falling back to chain")
            result = self._chain_reason(plan, context, result)

        logger.info(
            f"Reasoning complete: decision={result.decision.value}, "
            f"confidence={result.confidence:.2f}",
        )

        return result

    # ── Reasoning Strategies ──

    def _rule_based_reason(
        self,
        plan: Plan,
        context: Optional[Dict[str, Any]],
        result: ReasoningResult,
    ) -> ReasoningResult:
        """Rule-based reasoning: apply predefined rules to plan."""
        step = ReasoningStep(
            mode=ReasoningMode.RULE_BASED,
            input={"plan_id": plan.plan_id, "step_count": plan.step_count},
            explanation=f"Applied rule-based analysis to plan with {plan.step_count} steps",
        )

        # Rule: Empty plan is invalid
        if plan.step_count == 0:
            step.confidence = 1.0
            step.output = {"valid": False, "reason": "empty plan"}
            result.decision = DecisionType.ABORT
            result.decision_rationale = "Plan has no steps to execute"
            result.confidence = 1.0
        # Rule: Single step - proceed
        elif plan.step_count == 1:
            step.confidence = 0.9
            step.output = {"valid": True}
            result.decision = DecisionType.PROCEED
            result.decision_rationale = "Single step plan, proceeding"
            result.confidence = 0.9
        # Rule: Multi-step - check dependencies
        else:
            issues = plan.validate()
            if issues:
                step.confidence = 0.6
                step.output = {"valid": False, "issues": issues}
                result.decision = DecisionType.MODIFY
                result.decision_rationale = f"Plan has {len(issues)} validation issues"
                result.confidence = 0.6
            else:
                step.confidence = 0.85
                step.output = {"valid": True}
                result.decision = DecisionType.PROCEED
                result.decision_rationale = "Valid multi-step plan, proceeding"
                result.confidence = 0.85

        result.add_step(step)
        return result

    def _chain_reason(
        self,
        plan: Plan,
        context: Optional[Dict[str, Any]],
        result: ReasoningResult,
    ) -> ReasoningResult:
        """Chain reasoning: step-by-step analysis of each plan step."""
        for i, plan_step in enumerate(plan.steps):
            step = ReasoningStep(
                mode=ReasoningMode.CHAIN,
                input={"step": plan_step.name, "step_type": plan_step.step_type.value},
                explanation=f"Analyzed step [{i+1}/{plan.step_count}]: {plan_step.name}",
                confidence=0.8,
                output={"index": i, "ready": True},
            )
            result.add_step(step)

        # Final decision based on chain analysis
        if all(s.confidence > 0.5 for s in result.chain):
            result.decision = DecisionType.PROCEED
            result.decision_rationale = "All steps analyzed and validated"
            result.confidence = min(s.confidence for s in result.chain)
        else:
            result.decision = DecisionType.MODIFY
            result.decision_rationale = "Some steps have low confidence"
            result.confidence = 0.5

        return result

    def _reflection_reason(
        self,
        plan: Plan,
        context: Optional[Dict[str, Any]],
        result: ReasoningResult,
    ) -> ReasoningResult:
        """Reflection reasoning: self-critique the plan for improvement."""
        # First pass: analyze
        analysis = ReasoningStep(
            mode=ReasoningMode.REFLECTION,
            input={"plan_id": plan.plan_id},
            explanation=f"Initial analysis of plan with {plan.step_count} steps",
            confidence=0.8,
        )
        result.add_step(analysis)

        # Second pass: critique
        critique_points = []
        if plan.step_count > 10:
            critique_points.append("Plan has many steps, consider simplifying")
        if plan.total_estimated_seconds > 300:
            critique_points.append("Estimated duration is long, consider optimizing")

        critique = ReasoningStep(
            mode=ReasoningMode.REFLECTION,
            input={"analysis": analysis.output},
            explanation=f"Self-critique found {len(critique_points)} improvement points",
            confidence=0.7,
            output={"critiques": critique_points},
        )
        result.add_step(critique)

        # Decision
        if critique_points:
            result.decision = DecisionType.PROCEED
            result.decision_rationale = f"Proceeding with {len(critique_points)} suggestions"
            result.suggestions = critique_points
            result.confidence = 0.7
        else:
            result.decision = DecisionType.PROCEED
            result.decision_rationale = "Plan looks good, proceeding"
            result.confidence = 0.85

        return result

    # ── Strategy Registration ──

    def register_strategy(self, mode: ReasoningMode, strategy: Callable) -> None:
        """Register a custom reasoning strategy.

        Args:
            mode: The reasoning mode identifier.
            strategy: Callable that implements the reasoning logic.
        """
        self._strategy_registry[mode] = strategy
        logger.info(f"Registered reasoning strategy: {mode.value}")

    # ── Status ──

    def get_status(self) -> Dict[str, Any]:
        """Get reasoning engine status."""
        return {
            "total_reasoning_runs": self._result_count,
            "available_modes": [m.value for m in self._strategy_registry],
        }
