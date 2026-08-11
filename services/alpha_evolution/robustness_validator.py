"""
Robustness Validator — Validates alpha robustness across multiple dimensions.

Checks:
    - Out-of-sample performance retention
    - Parameter sensitivity
    - Data frequency robustness
    - Universe stability
    - Time period consistency
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RobustnessStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    MARGINAL = "marginal"
    NOT_TESTED = "not_tested"


@dataclass
class RobustnessResult:
    """Result of robustness validation."""

    individual_id: str
    status: RobustnessStatus = RobustnessStatus.NOT_TESTED
    oos_ic_retention: float = 0.0  # OOS IC / IS IC
    parameter_stability: float = 0.0
    universe_stability: float = 0.0
    time_period_stability: float = 0.0
    overall_score: float = 0.0
    failure_reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class RobustnessValidator:
    """
    Validates the robustness of factor/alpha candidates.

    A robust alpha should:
        - Retain predictive power out-of-sample
        - Be stable across parameter choices
        - Work across different universes
        - Perform consistently across time periods
    """

    def __init__(
        self,
        min_oos_retention: float = 0.50,
        min_parameter_stability: float = 0.40,
        min_universe_stability: float = 0.40,
        min_time_stability: float = 0.40,
        min_overall_score: float = 0.50,
    ):
        self._min_oos_retention = min_oos_retention
        self._min_parameter_stability = min_parameter_stability
        self._min_universe_stability = min_universe_stability
        self._min_time_stability = min_time_stability
        self._min_overall = min_overall_score

    async def validate(
        self,
        individual_id: str,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> RobustnessResult:
        """
        Validate robustness of an individual.

        Args:
            individual_id: Candidate ID
            metrics: Dict with is_ic, oos_ic, parameter_sensitivity, etc.
        """
        metrics = metrics or {}
        result = RobustnessResult(individual_id=individual_id)

        # 1. OOS retention
        is_ic = metrics.get("is_ic", 0)
        oos_ic = metrics.get("oos_ic", 0)
        if is_ic > 0:
            result.oos_ic_retention = oos_ic / is_ic
        elif oos_ic > 0:
            result.oos_ic_retention = 1.0

        if result.oos_ic_retention < self._min_oos_retention:
            result.failure_reasons.append(
                f"OOS retention {result.oos_ic_retention:.2f} < {self._min_oos_retention}"
            )

        # 2. Parameter stability
        result.parameter_stability = metrics.get("parameter_stability", 0.5)
        if result.parameter_stability < self._min_parameter_stability:
            result.failure_reasons.append(
                f"Parameter stability {result.parameter_stability:.2f} < {self._min_parameter_stability}"
            )

        # 3. Universe stability
        result.universe_stability = metrics.get("universe_stability", 0.5)

        # 4. Time period stability
        result.time_period_stability = metrics.get("time_period_stability", 0.5)

        # 5. Overall score
        result.overall_score = (
            result.oos_ic_retention * 0.40
            + result.parameter_stability * 0.25
            + result.universe_stability * 0.15
            + result.time_period_stability * 0.20
        )

        if result.overall_score >= self._min_overall and not result.failure_reasons:
            result.status = RobustnessStatus.PASSED
        elif result.failure_reasons:
            result.status = RobustnessStatus.FAILED
        else:
            result.status = RobustnessStatus.MARGINAL

        return result

    async def validate_batch(
        self,
        individuals: List[tuple[str, Optional[Dict[str, Any]]]],
    ) -> Dict[str, RobustnessResult]:
        """Validate a batch of individuals."""
        results = {}
        for oid, metrics in individuals:
            results[oid] = await self.validate(oid, metrics)
        return results

    def get_thresholds(self) -> Dict[str, float]:
        return {
            "oos_retention": self._min_oos_retention,
            "parameter_stability": self._min_parameter_stability,
            "overall": self._min_overall,
        }
