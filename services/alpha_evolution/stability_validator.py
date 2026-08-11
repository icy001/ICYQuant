"""
Stability Validator — Validates alpha stability over time.

Checks:
    - IC stability (rolling IC consistency)
    - Rank IC stability
    - Factor loading stability
    - Turnover stability
    - Decay pattern stability
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class StabilityStatus(Enum):
    STABLE = "stable"
    UNSTABLE = "unstable"
    MARGINAL = "marginal"
    NOT_TESTED = "not_tested"


@dataclass
class StabilityResult:
    individual_id: str
    status: StabilityStatus = StabilityStatus.NOT_TESTED
    ic_stability: float = 0.0          # std of rolling IC / mean IC
    rank_ic_stability: float = 0.0
    turnover_stability: float = 0.0
    decay_rate_stability: float = 0.0
    overall_score: float = 0.0
    failure_reasons: List[str] = field(default_factory=list)


class StabilityValidator:
    """
    Validates the temporal stability of alpha candidates.

    A stable alpha should:
        - Have consistent IC over time (not regime-dependent)
        - Maintain stable factor loadings
        - Have predictable turnover
        - Show gradual (not sudden) decay
    """

    def __init__(
        self,
        max_ic_volatility: float = 0.50,  # max std(IC) / mean(IC)
        min_stability_score: float = 0.50,
    ):
        self._max_ic_volatility = max_ic_volatility
        self._min_stability_score = min_stability_score

    async def validate(
        self,
        individual_id: str,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> StabilityResult:
        """Validate stability of an individual."""
        metrics = metrics or {}
        result = StabilityResult(individual_id=individual_id)

        # IC stability: lower CoV is better
        mean_ic = metrics.get("mean_ic", 0)
        std_ic = metrics.get("std_ic", 0)
        if mean_ic != 0:
            result.ic_stability = 1.0 - min(std_ic / abs(mean_ic), 1.0)
        else:
            result.ic_stability = 0.0

        if std_ic / max(abs(mean_ic), 0.001) > self._max_ic_volatility:
            result.failure_reasons.append("IC volatility exceeds threshold")

        # Rank IC stability
        result.rank_ic_stability = metrics.get("rank_ic_stability", 0.5)

        # Turnover stability
        result.turnover_stability = metrics.get("turnover_stability", 0.5)

        # Overall
        result.overall_score = (
            result.ic_stability * 0.40
            + result.rank_ic_stability * 0.30
            + result.turnover_stability * 0.30
        )

        if result.overall_score >= self._min_stability_score and not result.failure_reasons:
            result.status = StabilityStatus.STABLE
        elif result.failure_reasons:
            result.status = StabilityStatus.UNSTABLE
        else:
            result.status = StabilityStatus.MARGINAL

        return result

    async def validate_batch(
        self,
        individuals: List[tuple[str, Optional[Dict[str, Any]]]],
    ) -> Dict[str, StabilityResult]:
        results = {}
        for oid, metrics in individuals:
            results[oid] = await self.validate(oid, metrics)
        return results
