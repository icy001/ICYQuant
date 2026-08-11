"""Confidence Engine — computes a unified confidence score for autonomous decisions.

Pipeline:
    Research Score + Risk Score + Execution Score -> ConfidenceEngine.evaluate()
        -> Weighted aggregation
        -> Output ConfidenceScore
        -> Low confidence triggers escalation / human approval
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceScore:
    """Unified confidence score for a decision.

    Attributes:
        score_id: Unique identifier.
        research_score: Research quality score (0.0-1.0).
        risk_score: Risk assessment score (0.0-1.0).
        execution_score: Execution feasibility score (0.0-1.0).
        overall: Weighted overall confidence (0.0-1.0).
        requires_approval: Whether this score triggers HITL approval.
        detail: Human-readable detail.
        evaluated_at: Evaluation timestamp.
    """

    score_id: str = ""
    research_score: float = 0.0
    risk_score: float = 0.0
    execution_score: float = 0.0
    overall: float = 0.0
    requires_approval: bool = True
    detail: str = ""
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_high_confidence(self) -> bool:
        return self.overall >= 0.80

    @property
    def is_medium_confidence(self) -> bool:
        return 0.50 <= self.overall < 0.80

    @property
    def is_low_confidence(self) -> bool:
        return self.overall < 0.50


class ConfidenceEngine:
    """Computes unified confidence scores for autonomous decisions.

    Aggregates research, risk, and execution quality into a single
    confidence score that drives HITL approval decisions.

    Supports:
        - Multi-dimensional confidence scoring
        - Weighted aggregation (research 40%, risk 35%, execution 25%)
        - Threshold-based approval triggering
        - Detail explanations

    Usage:
        engine = ConfidenceEngine()
        await engine.initialize()
        score = engine.evaluate(research=0.85, risk=0.70, execution=0.90)
        if score.is_high_confidence:
            auto_approve()
        else:
            request_human_approval()
    """

    def __init__(
        self,
        research_weight: float = 0.40,
        risk_weight: float = 0.35,
        execution_weight: float = 0.25,
        approval_threshold: float = 0.80,
    ) -> None:
        self._research_weight = research_weight
        self._risk_weight = risk_weight
        self._execution_weight = execution_weight
        self._approval_threshold = approval_threshold
        self._scores: list[ConfidenceScore] = []
        self._counter: int = 0
        self._initialized: bool = False
        logger.info(
            "ConfidenceEngine created (weights: R=%.0f%% K=%.0f%% X=%.0f%%, threshold=%.0f%%)",
            research_weight * 100, risk_weight * 100, execution_weight * 100, approval_threshold * 100,
        )

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("ConfidenceEngine initialized")

    async def shutdown(self) -> None:
        self._scores.clear()
        self._initialized = False
        logger.info("ConfidenceEngine shutdown complete")

    def evaluate(
        self,
        research_score: float = 0.0,
        risk_score: float = 0.0,
        execution_score: float = 0.0,
    ) -> ConfidenceScore:
        """Compute a unified confidence score.

        Args:
            research_score: Research quality (0.0-1.0).
            risk_score: Risk assessment (0.0-1.0).
            execution_score: Execution feasibility (0.0-1.0).

        Returns:
            ConfidenceScore with overall rating.
        """
        overall = (
            research_score * self._research_weight
            + risk_score * self._risk_weight
            + execution_score * self._execution_weight
        )

        self._counter += 1
        score = ConfidenceScore(
            score_id=f"conf_{self._counter}",
            research_score=research_score,
            risk_score=risk_score,
            execution_score=execution_score,
            overall=round(overall, 4),
            requires_approval=overall < self._approval_threshold,
            detail=self._generate_detail(research_score, risk_score, execution_score, overall),
        )
        self._scores.append(score)
        logger.info(
            "Confidence evaluated: overall=%.2f (R=%.2f, K=%.2f, X=%.2f), requires_approval=%s",
            score.overall, research_score, risk_score, execution_score, score.requires_approval,
        )
        return score

    @staticmethod
    def _generate_detail(research: float, risk: float, execution: float, overall: float) -> str:
        parts = []
        if research < 0.7:
            parts.append("research quality below target")
        if risk < 0.7:
            parts.append("risk score elevated")
        if execution < 0.7:
            parts.append("execution feasibility low")
        if not parts:
            parts.append("all scores within acceptable range")
        return f"Overall {overall:.2f}: " + "; ".join(parts)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "total_evaluations": len(self._scores),
            "threshold": self._approval_threshold,
        }
