"""
Turnover Analyzer — Analyzes alpha turnover and its implications.

Turnover measures how frequently the alpha changes positions.
High turnover means:
    - Higher transaction costs
    - Lower net returns
    - Potentially unstable signals
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TurnoverLevel(Enum):
    LOW = "low"           # < 20% daily
    MODERATE = "moderate"  # 20-50%
    HIGH = "high"          # 50-100%
    EXTREME = "extreme"    # > 100%


@dataclass
class TurnoverResult:
    individual_id: str
    daily_turnover: float = 0.0
    weekly_turnover: float = 0.0
    monthly_turnover: float = 0.0
    level: TurnoverLevel = TurnoverLevel.MODERATE
    estimated_cost_bps: float = 0.0
    overall_score: float = 0.0
    warnings: List[str] = field(default_factory=list)


class TurnoverAnalyzer:
    """
    Analyzes alpha turnover rates.

    Lower turnover is generally preferred (lower costs, more stable),
    but extremely low turnover may miss opportunities.
    """

    def __init__(
        self,
        max_daily_turnover: float = 0.50,
        max_monthly_turnover: float = 3.0,
    ):
        self._max_daily = max_daily_turnover
        self._max_monthly = max_monthly_turnover

    async def analyze(
        self,
        individual_id: str,
        metrics: Optional[Dict[str, float]] = None,
    ) -> TurnoverResult:
        """Analyze turnover of an alpha."""
        metrics = metrics or {}
        result = TurnoverResult(individual_id=individual_id)

        result.daily_turnover = metrics.get("daily_turnover", 0)
        result.weekly_turnover = metrics.get("weekly_turnover", 0)
        result.monthly_turnover = metrics.get("monthly_turnover", 0)

        # Classify level
        if result.daily_turnover < 0.20:
            result.level = TurnoverLevel.LOW
        elif result.daily_turnover < 0.50:
            result.level = TurnoverLevel.MODERATE
        elif result.daily_turnover < 1.0:
            result.level = TurnoverLevel.HIGH
        else:
            result.level = TurnoverLevel.EXTREME

        # Estimate cost
        result.estimated_cost_bps = result.daily_turnover * 10  # rough estimate

        if result.daily_turnover > self._max_daily:
            result.warnings.append(f"Daily turnover {result.daily_turnover:.2f} > max {self._max_daily}")

        if result.monthly_turnover > self._max_monthly:
            result.warnings.append(f"Monthly turnover {result.monthly_turnover:.1f} > max {self._max_monthly}")

        # Score (lower turnover = higher score, up to a point)
        if result.level == TurnoverLevel.LOW:
            result.overall_score = 0.9
        elif result.level == TurnoverLevel.MODERATE:
            result.overall_score = 0.8
        elif result.level == TurnoverLevel.HIGH:
            result.overall_score = 0.5
        else:
            result.overall_score = 0.2

        return result

    async def analyze_batch(
        self,
        individuals: List[tuple[str, Optional[Dict[str, float]]]],
    ) -> Dict[str, TurnoverResult]:
        results = {}
        for oid, metrics in individuals:
            results[oid] = await self.analyze(oid, metrics)
        return results
