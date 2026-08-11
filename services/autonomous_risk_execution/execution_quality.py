"""
Execution Quality — composite scoring of execution performance.

Computes a single quality score from multiple dimensions:
    - Fill rate
    - Slippage vs expected
    - Implementation shortfall
    - Price improvement
    - Timing efficiency
    - Cost efficiency
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class QualityScores:
    """Dimension-level quality scores."""
    fill_rate_score: float = 0.0
    slippage_score: float = 0.0
    shortfall_score: float = 0.0
    timing_score: float = 0.0
    cost_score: float = 0.0
    composite: float = 0.0


@dataclass
class ExecutionQualityResult:
    """Complete execution quality result."""
    id: str = field(default_factory=lambda: str(uuid4()))
    order_id: str = ""
    scores: QualityScores = field(default_factory=QualityScores)
    grade: str = "C"  # A+, A, B, C, D, F
    recommendations: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class ExecutionQuality:
    """
    Composite execution quality scoring.

    Score dimensions (0-1.0, higher is better):
        - Fill rate: filled / target (1.0 = fully filled)
        - Slippage: 1 - |realized| / max(2×|expected|, 50bps)
        - Shortfall: 1 - |IS| / 50bps
        - Timing: 1 - actual_time / max_expected_time
        - Cost: 1 - total_cost / max_cost_budget

    Grade scale:
        ≥ 0.90: A+, ≥ 0.80: A, ≥ 0.65: B, ≥ 0.50: C, ≥ 0.35: D, else F
    """

    WEIGHTS = {
        "fill_rate": 0.25,
        "slippage": 0.25,
        "shortfall": 0.20,
        "timing": 0.15,
        "cost": 0.15,
    }

    def __init__(self) -> None:
        self._results: list[ExecutionQualityResult] = []

    async def score(
        self,
        order_id: str,
        fill_rate: float,
        realized_slippage_bps: float,
        expected_slippage_bps: float,
        shortfall_bps: float,
        execution_time_seconds: float,
        max_expected_seconds: float,
        total_cost_bps: float,
        cost_budget_bps: float = 50.0,
    ) -> ExecutionQualityResult:
        """Compute composite execution quality score."""
        scores = QualityScores()

        # Fill rate score (0-1)
        scores.fill_rate_score = min(1.0, fill_rate)

        # Slippage score (0-1)
        max_acceptable = max(2 * abs(expected_slippage_bps), 50)
        scores.slippage_score = max(0, 1 - abs(realized_slippage_bps) / max_acceptable)

        # Shortfall score (0-1)
        scores.shortfall_score = max(0, 1 - abs(shortfall_bps) / 50)

        # Timing score (0-1)
        scores.timing_score = max(0, 1 - execution_time_seconds / max(max_expected_seconds, 1))

        # Cost score (0-1)
        scores.cost_score = max(0, 1 - total_cost_bps / max(cost_budget_bps, 1))

        # Composite
        scores.composite = (
            scores.fill_rate_score * self.WEIGHTS["fill_rate"]
            + scores.slippage_score * self.WEIGHTS["slippage"]
            + scores.shortfall_score * self.WEIGHTS["shortfall"]
            + scores.timing_score * self.WEIGHTS["timing"]
            + scores.cost_score * self.WEIGHTS["cost"]
        )

        # Grade
        grade = "F"
        if scores.composite >= 0.90:
            grade = "A+"
        elif scores.composite >= 0.80:
            grade = "A"
        elif scores.composite >= 0.65:
            grade = "B"
        elif scores.composite >= 0.50:
            grade = "C"
        elif scores.composite >= 0.35:
            grade = "D"

        # Recommendations
        recs = []
        if scores.fill_rate_score < 0.80:
            recs.append("Improve fill rate — consider more aggressive pricing")
        if scores.slippage_score < 0.60:
            recs.append("Reduce slippage — slower execution or limit orders")
        if scores.shortfall_score < 0.60:
            recs.append("Reduce shortfall — earlier execution or better timing")
        if scores.cost_score < 0.50:
            recs.append("Reduce costs — review venue and strategy selection")

        result = ExecutionQualityResult(
            order_id=order_id,
            scores=scores,
            grade=grade,
            recommendations=recs,
        )
        self._results.append(result)
        if len(self._results) > 500:
            self._results = self._results[-250:]

        return result

    async def get_aggregate_grade(self) -> dict:
        """Get aggregate quality distribution."""
        if not self._results:
            return {"avg_score": 0, "grade_distribution": {}}

        grades = [r.grade for r in self._results]
        avg = sum(r.scores.composite for r in self._results) / len(self._results)
        dist = {g: grades.count(g) for g in ["A+", "A", "B", "C", "D", "F"]}

        return {"avg_score": avg, "grade_distribution": dist}
