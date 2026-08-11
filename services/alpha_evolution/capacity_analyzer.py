"""
Capacity Analyzer — Estimates alpha capacity (maximum AUM).

Factors affecting capacity:
    - Liquidity (ADV, bid-ask spread)
    - Market impact
    - Universe size
    - Turnover
    - Position concentration

Critical to distinguish "paper alphas" from "real alphas".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CapacityLevel(Enum):
    LARGE = "large"       # > $1B
    MEDIUM = "medium"     # $100M - $1B
    SMALL = "small"       # $10M - $100M
    MICRO = "micro"       # < $10M
    UNKNOWN = "unknown"


@dataclass
class CapacityResult:
    individual_id: str
    estimated_capacity_million: float = 0.0
    level: CapacityLevel = CapacityLevel.UNKNOWN
    adv_constraint: float = 0.0
    impact_estimate_bps: float = 0.0
    realistic_return: float = 0.0
    overall_score: float = 0.0
    warnings: List[str] = field(default_factory=list)


class CapacityAnalyzer:
    """
    Estimates alpha capacity — the maximum capital it can deploy without
    significant market impact.

    A "great" alpha with $1M capacity is far less valuable than a
    "good" alpha with $1B capacity.
    """

    def __init__(
        self,
        min_capacity_million: float = 10.0,
        max_impact_bps: float = 5.0,
    ):
        self._min_capacity = min_capacity_million
        self._max_impact = max_impact_bps

    async def analyze(
        self,
        individual_id: str,
        metrics: Optional[Dict[str, float]] = None,
    ) -> CapacityResult:
        """Estimate alpha capacity."""
        metrics = metrics or {}
        result = CapacityResult(individual_id=individual_id)

        result.estimated_capacity_million = metrics.get("capacity_million", 0)
        result.adv_constraint = metrics.get("adv_constraint", 0)
        result.impact_estimate_bps = metrics.get("impact_bps", 0)

        # Classify level
        cap = result.estimated_capacity_million
        if cap > 1000:
            result.level = CapacityLevel.LARGE
        elif cap > 100:
            result.level = CapacityLevel.MEDIUM
        elif cap > 10:
            result.level = CapacityLevel.SMALL
        elif cap > 0:
            result.level = CapacityLevel.MICRO

        # Realistic return (gross - impact)
        gross_return = metrics.get("annual_return_pct", 0)
        result.realistic_return = max(0, gross_return - result.impact_estimate_bps / 100)

        if result.estimated_capacity_million < self._min_capacity:
            result.warnings.append(
                f"Capacity ${result.estimated_capacity_million:.0f}M < min ${self._min_capacity}M"
            )

        if result.impact_estimate_bps > self._max_impact:
            result.warnings.append(f"Impact {result.impact_estimate_bps:.1f}bps > max {self._max_impact}bps")

        # Score
        if result.level == CapacityLevel.LARGE:
            result.overall_score = 1.0
        elif result.level == CapacityLevel.MEDIUM:
            result.overall_score = 0.7
        elif result.level == CapacityLevel.SMALL:
            result.overall_score = 0.4
        else:
            result.overall_score = 0.1

        return result

    async def analyze_batch(
        self,
        individuals: List[tuple[str, Optional[Dict[str, float]]]],
    ) -> Dict[str, CapacityResult]:
        results = {}
        for oid, metrics in individuals:
            results[oid] = await self.analyze(oid, metrics)
        return results
