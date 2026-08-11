"""Reflection Engine — self-evaluation and iterative improvement loop.

Pipeline:
    Observation
        -> ReflectionEngine.evaluate()
        -> Self Evaluation (success criteria, quality assessment)
        -> Correction (if needed)
        -> Learning (update memory / strategy)
        -> Next Action Decision
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from services.ai_agent.tooling.tool_result import ToolResult

logger = logging.getLogger(__name__)


# ── Enums ──

class ReflectionOutcome(str, Enum):
    """Outcome of reflection evaluation."""

    SUCCESS = "success"  # Goal achieved
    PARTIAL = "partial"  # Partial success, needs more work
    FAILURE = "failure"  # Failed, needs correction
    NEEDS_CLARIFICATION = "needs_clarification"  # Need more info
    CONTINUE = "continue"  # Proceed to next step


class CorrectionType(str, Enum):
    """Type of correction to apply."""

    RETRY = "retry"  # Retry with same params
    RETRY_ADJUSTED = "retry_adjusted"  # Retry with adjusted params
    FALLBACK = "fallback"  # Use fallback tool
    REPLAN = "replan"  # Replan the entire task
    SKIP = "skip"  # Skip this step
    ABORT = "abort"  # Abort the task


# ── Reflection ──

@dataclass
class Reflection:
    """Result of a reflection evaluation."""

    reflection_id: str = ""
    outcome: ReflectionOutcome = ReflectionOutcome.SUCCESS
    correction: Optional[CorrectionType] = None

    # ── Analysis ──
    assessment: str = ""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    # ── Metrics ──
    quality_score: float = 0.0  # 0.0 to 1.0
    confidence: float = 1.0  # 0.0 to 1.0

    # ── Adjusted Params (for retry) ──
    adjusted_params: Dict[str, Any] = field(default_factory=dict)

    # ── Learning ──
    lessons_learned: List[str] = field(default_factory=list)

    # ── Timing ──
    reflected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_success(self) -> bool:
        return self.outcome == ReflectionOutcome.SUCCESS

    @property
    def needs_correction(self) -> bool:
        return self.correction is not None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "reflection_id": self.reflection_id,
            "outcome": self.outcome.value,
            "correction": self.correction.value if self.correction else None,
            "assessment": self.assessment,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "suggestions": self.suggestions,
            "quality_score": round(self.quality_score, 3),
            "confidence": round(self.confidence, 3),
            "adjusted_params": self.adjusted_params,
            "lessons_learned": self.lessons_learned,
            "reflected_at": self.reflected_at.isoformat(),
        }


# ── ReflectionEngine ──

class ReflectionEngine:
    """Self-evaluation engine for iterative improvement.

    Evaluates tool execution outcomes and generates reflections
    that guide the agent's next actions. Supports self-correction
    by suggesting parameter adjustments, fallbacks, or replanning.

    Supports:
        - Success/failure evaluation
        - Quality scoring
        - Correction suggestion
        - Parameter adjustment
        - Lesson learning
        - Next-action guidance

    Usage:
        engine = ReflectionEngine()
        reflection = await engine.evaluate(tool_result, goal="Run backtest")
        if reflection.needs_correction:
            adjusted_params = reflection.adjusted_params
    """

    def __init__(self) -> None:
        """Initialize the reflection engine."""
        self._history: List[Reflection] = []
        self._initialized: bool = False
        logger.info("ReflectionEngine created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the reflection engine."""
        self._initialized = True
        logger.info("ReflectionEngine initialized")

    async def shutdown(self) -> None:
        """Shutdown the reflection engine."""
        self._history.clear()
        self._initialized = False
        logger.info("ReflectionEngine shutdown complete")

    # ── Evaluation ──

    async def evaluate(
        self,
        result: ToolResult,
        goal: str = "",
        expected_outcome: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Reflection:
        """Evaluate a tool execution result and produce a reflection.

        Args:
            result: The tool execution result.
            goal: The original goal/intent.
            expected_outcome: Optional expected outcome for comparison.
            context: Optional evaluation context.

        Returns:
            A Reflection with evaluation and suggestions.
        """
        from uuid import uuid4

        reflection_id = uuid4().hex

        if result.success:
            return await self._evaluate_success(result, goal, expected_outcome, reflection_id)
        else:
            return await self._evaluate_failure(result, goal, reflection_id)

    async def evaluate_batch(
        self,
        results: List[ToolResult],
        goal: str = "",
    ) -> List[Reflection]:
        """Evaluate multiple tool results.

        Args:
            results: List of tool results.
            goal: The overall goal.

        Returns:
            List of reflections.
        """
        reflections = []
        for result in results:
            ref = await self.evaluate(result, goal=goal)
            reflections.append(ref)
            self._history.append(ref)
        return reflections

    # ── Private: Success Evaluation ──

    async def _evaluate_success(
        self,
        result: ToolResult,
        goal: str,
        expected_outcome: Optional[Dict[str, Any]],
        reflection_id: str,
    ) -> Reflection:
        """Evaluate a successful execution.

        Args:
            result: The successful tool result.
            goal: The original goal.
            expected_outcome: Expected outcome.
            reflection_id: Reflection identifier.

        Returns:
            A Reflection.
        """
        quality = self._assess_quality(result, expected_outcome)

        assessment_parts: List[str] = []
        strengths: List[str] = []
        weaknesses: List[str] = []

        if result.from_cache:
            strengths.append("Result served from cache (fast)")
        if result.latency_ms < 100:
            strengths.append(f"Fast execution ({result.latency_ms:.0f}ms)")
        elif result.latency_ms > 5000:
            weaknesses.append(f"Slow execution ({result.latency_ms:.0f}ms)")

        if result.data:
            strengths.append("Valid output data returned")
        else:
            weaknesses.append("No output data returned")

        if result.warnings:
            weaknesses.append(f"Warnings: {result.warnings}")

        # Build assessment
        if goal:
            assessment_parts.append(f"Goal '{goal}': achieved")
        assessment_parts.append(f"Tool '{result.tool_name}' executed successfully")

        if strengths:
            assessment_parts.append(f"Strengths: {', '.join(strengths)}")
        if weaknesses:
            assessment_parts.append(f"Weaknesses: {', '.join(weaknesses)}")

        reflection = Reflection(
            reflection_id=reflection_id,
            outcome=ReflectionOutcome.SUCCESS,
            assessment=". ".join(assessment_parts),
            strengths=strengths,
            weaknesses=weaknesses,
            quality_score=quality,
            confidence=0.95,
            suggestions=["Proceed to next step"] if not weaknesses else [],
        )

        logger.info(f"Reflection SUCCESS for {result.tool_name}: quality={quality:.2f}")
        self._history.append(reflection)
        return reflection

    # ── Private: Failure Evaluation ──

    async def _evaluate_failure(
        self,
        result: ToolResult,
        goal: str,
        reflection_id: str,
    ) -> Reflection:
        """Evaluate a failed execution.

        Args:
            result: The failed tool result.
            goal: The original goal.
            reflection_id: Reflection identifier.

        Returns:
            A Reflection with correction suggestion.
        """
        outcome = ReflectionOutcome.FAILURE
        correction: Optional[CorrectionType] = None
        suggestions: List[str] = []
        lessons: List[str] = []

        # Determine correction based on error type
        if result.error_type == "timeout":
            outcome = ReflectionOutcome.PARTIAL
            correction = CorrectionType.RETRY_ADJUSTED
            suggestions.append("Reduce input size or increase timeout")
            lessons.append(f"Tool '{result.tool_name}' may need more time for complex inputs")

        elif result.error_type == "validation":
            outcome = ReflectionOutcome.FAILURE
            correction = CorrectionType.RETRY_ADJUSTED
            suggestions.append("Review and fix input parameters")
            lessons.append(f"Input validation failed for '{result.tool_name}': {result.error}")

        elif result.error_type == "permission":
            outcome = ReflectionOutcome.FAILURE
            correction = CorrectionType.FALLBACK
            suggestions.append("Use a fallback tool with lower permission requirements")
            lessons.append(f"Permission denied for '{result.tool_name}'")

        elif result.error_type == "runtime":
            outcome = ReflectionOutcome.FAILURE
            correction = CorrectionType.RETRY
            suggestions.append("Retry the operation (transient error possible)")
            lessons.append(f"Runtime error in '{result.tool_name}': {result.error}")

        else:
            outcome = ReflectionOutcome.FAILURE
            correction = CorrectionType.FALLBACK
            suggestions.append("Try alternative approach or fallback tool")
            lessons.append(f"Unknown error in '{result.tool_name}': {result.error}")

        assessment = (
            f"Goal '{goal}': not achieved. "
            f"Tool '{result.tool_name}' failed with error: {result.error}. "
            f"Suggested correction: {correction.value if correction else 'none'}."
        )

        reflection = Reflection(
            reflection_id=reflection_id,
            outcome=outcome,
            correction=correction,
            assessment=assessment,
            weaknesses=[f"Error: {result.error}"],
            suggestions=suggestions,
            quality_score=0.0,
            confidence=0.3,
            lessons_learned=lessons,
        )

        logger.info(
            f"Reflection FAILURE for {result.tool_name}: "
            f"correction={correction.value if correction else 'none'}"
        )
        self._history.append(reflection)
        return reflection

    # ── Quality Assessment ──

    @staticmethod
    def _assess_quality(
        result: ToolResult,
        expected_outcome: Optional[Dict[str, Any]],
    ) -> float:
        """Assess the quality of a result.

        Args:
            result: The tool result.
            expected_outcome: Optional expected outcome.

        Returns:
            Quality score (0.0 to 1.0).
        """
        score = 1.0

        # Penalties
        if result.latency_ms > 10000:
            score -= 0.2
        elif result.latency_ms > 5000:
            score -= 0.1

        if result.warnings:
            score -= 0.05 * min(len(result.warnings), 4)

        if result.from_cache:
            score -= 0.05  # Slight penalty for stale data

        if result.data is None:
            score -= 0.3

        return max(0.0, min(1.0, score))

    # ── History ──

    def get_history(self, limit: int = 50) -> List[Reflection]:
        """Get reflection history.

        Args:
            limit: Maximum results.

        Returns:
            List of reflections.
        """
        return self._history[-limit:]

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get reflection engine status."""
        recent = self._history[-10:] if self._history else []
        return {
            "total_reflections": len(self._history),
            "recent_outcomes": [r.outcome.value for r in recent],
            "recent_quality_avg": (
                round(sum(r.quality_score for r in recent) / len(recent), 3)
                if recent
                else 0.0
            ),
            "initialized": self._initialized,
        }
