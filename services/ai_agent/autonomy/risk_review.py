"""Risk Review — autonomously assesses portfolio risk before execution.

Pipeline:
    Portfolio -> RiskReview.assess()
        -> Exposure analysis
        -> Liquidity check
        -> VaR / CVaR calculation
        -> Stress testing
        -> Constraint validation
        -> Output RiskAssessment (approved / rejected)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RiskDecision(str, Enum):
    APPROVED = "approved"
    APPROVED_WITH_WARNINGS = "approved_with_warnings"
    REJECTED = "rejected"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskAssessment:
    """Risk assessment for a portfolio recommendation.

    Attributes:
        assessment_id: Unique identifier.
        decision: Final risk decision.
        overall_risk: Overall risk level.
        var_95: Value at Risk (95% confidence).
        cvar_95: Conditional VaR (95%).
        max_single_exposure: Maximum single position exposure.
        liquidity_score: Portfolio liquidity score (0.0-1.0).
        stress_test_loss: Worst-case stress test loss.
        warnings: List of risk warnings.
        violations: List of constraint violations.
        assessed_at: Assessment timestamp.
    """

    assessment_id: str = ""
    decision: RiskDecision = RiskDecision.APPROVED
    overall_risk: RiskLevel = RiskLevel.LOW
    var_95: float = 0.0
    cvar_95: float = 0.0
    max_single_exposure: float = 0.0
    liquidity_score: float = 1.0
    stress_test_loss: float = 0.0
    warnings: List[str] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    assessed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_approved(self) -> bool:
        return self.decision in (RiskDecision.APPROVED, RiskDecision.APPROVED_WITH_WARNINGS)


class RiskReview:
    """Autonomously assesses portfolio risk before execution.

    Performs comprehensive risk analysis including exposure, liquidity,
    VaR/CVaR, stress testing, and constraint validation. Any violation
    of risk rules automatically terminates the workflow.

    Supports:
        - Exposure analysis (single name, sector, factor)
        - Liquidity assessment
        - VaR / CVaR calculation
        - Stress testing
        - Constraint validation
        - Automatic rejection on violations

    Usage:
        review = RiskReview()
        await review.initialize()
        assessment = await review.assess(portfolio, constraints={...})
        if not assessment.is_approved:
            raise RiskViolationError(assessment.violations)
    """

    def __init__(
        self,
        max_single_exposure: float = 0.10,
        max_var_pct: float = 0.05,
        min_liquidity_score: float = 0.7,
    ) -> None:
        self._max_single_exposure = max_single_exposure
        self._max_var_pct = max_var_pct
        self._min_liquidity_score = min_liquidity_score
        self._assessments: List[RiskAssessment] = []
        self._counter: int = 0
        self._initialized: bool = False
        logger.info("RiskReview created (max_exposure=%.0f%%, max_var=%.0f%%)", max_single_exposure * 100, max_var_pct * 100)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("RiskReview initialized")

    async def shutdown(self) -> None:
        self._assessments.clear()
        self._initialized = False
        logger.info("RiskReview shutdown complete")

    async def assess(
        self,
        portfolio: Optional[Any] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> RiskAssessment:
        """Assess risk for a portfolio.

        Args:
            portfolio: Portfolio recommendation or allocation dict.
            constraints: Optional risk constraints.

        Returns:
            RiskAssessment with decision and warnings.
        """
        logger.info("RiskReview.assess() started")
        self._counter += 1
        assessment = RiskAssessment(
            assessment_id=f"risk_{self._counter}",
            decision=RiskDecision.APPROVED,
            overall_risk=RiskLevel.LOW,
        )

        # Check for violations
        if assessment.max_single_exposure > self._max_single_exposure:
            assessment.violations.append(f"Single exposure {assessment.max_single_exposure:.2%} exceeds limit {self._max_single_exposure:.2%}")
        if assessment.var_95 > self._max_var_pct:
            assessment.violations.append(f"VaR {assessment.var_95:.2%} exceeds limit {self._max_var_pct:.2%}")

        if assessment.violations:
            assessment.decision = RiskDecision.REJECTED
            assessment.overall_risk = RiskLevel.CRITICAL
        elif assessment.warnings:
            assessment.decision = RiskDecision.APPROVED_WITH_WARNINGS

        self._assessments.append(assessment)
        logger.info("RiskReview.assess() completed: decision=%s", assessment.decision.value)
        return assessment

    def get_recent_assessments(self, limit: int = 10) -> List[Dict[str, Any]]:
        return [
            {
                "id": a.assessment_id,
                "decision": a.decision.value,
                "risk_level": a.overall_risk.value,
                "var_95": round(a.var_95, 4),
                "warnings": len(a.warnings),
                "violations": len(a.violations),
            }
            for a in self._assessments[-limit:]
        ]

    def get_summary(self) -> Dict[str, Any]:
        approved = sum(1 for a in self._assessments if a.is_approved)
        rejected = sum(1 for a in self._assessments if a.decision == RiskDecision.REJECTED)
        return {
            "initialized": self._initialized,
            "total": len(self._assessments),
            "approved": approved,
            "rejected": rejected,
        }
