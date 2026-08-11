"""
Decay Analyzer — Analyzes alpha signal decay over time horizons.

Measures how quickly an alpha's predictive power decays:
    - 1-day IC
    - 5-day IC
    - 20-day IC
    - 60-day IC
    - 120-day IC

A good alpha should show gradual (not instant) decay.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

HORIZONS = [1, 5, 10, 20, 60, 120]


@dataclass
class DecayResult:
    individual_id: str
    ic_by_horizon: Dict[int, float] = field(default_factory=dict)
    half_life_days: Optional[float] = None
    decay_rate: float = 0.0          # avg decay per doubling of horizon
    decay_type: str = "unknown"      # "fast", "gradual", "stable", "none"
    overall_score: float = 0.0
    warnings: List[str] = field(default_factory=list)


class DecayAnalyzer:
    """
    Analyzes alpha signal decay across time horizons.

    Measures IC at various forward horizons to determine
    how quickly the signal loses predictive power.
    """

    def __init__(
        self,
        min_half_life_days: float = 5.0,
        max_decay_rate: float = 0.50,
    ):
        self._min_half_life = min_half_life_days
        self._max_decay_rate = max_decay_rate

    async def analyze(
        self,
        individual_id: str,
        horizon_ic: Optional[Dict[int, float]] = None,
    ) -> DecayResult:
        """
        Analyze alpha decay.

        Args:
            individual_id: Candidate ID
            horizon_ic: Dict of horizon_days → IC
        """
        horizon_ic = horizon_ic or {}
        result = DecayResult(individual_id=individual_id)

        if not horizon_ic:
            return result

        result.ic_by_horizon = horizon_ic

        # Find half-life (horizon where IC drops to half of 1-day IC)
        ic_1d = horizon_ic.get(1, 0)
        if ic_1d > 0:
            half_ic = ic_1d / 2
            for horizon in sorted(horizon_ic.keys()):
                if horizon_ic[horizon] <= half_ic:
                    result.half_life_days = float(horizon)
                    break

        # Decay rate per doubling of horizon
        if ic_1d > 0 and len(horizon_ic) >= 2:
            h1 = 1
            h2 = max(h for h in horizon_ic if h > h1)
            ic_h2 = horizon_ic.get(h2, 0)
            if ic_h2 > 0:
                doublings = max(1, h2 // h1)
                result.decay_rate = (ic_1d - ic_h2) / (ic_1d * doublings)

        # Classify decay
        if result.half_life_days is None:
            result.decay_type = "none"
        elif result.half_life_days < 5:
            result.decay_type = "fast"
            result.warnings.append(f"Fast decay: half-life = {result.half_life_days}d")
        elif result.half_life_days < 20:
            result.decay_type = "gradual"
        else:
            result.decay_type = "stable"

        if result.half_life_days and result.half_life_days < self._min_half_life:
            result.warnings.append(
                f"Half-life {result.half_life_days:.0f}d < min {self._min_half_life}d"
            )

        result.overall_score = 1.0 if result.decay_type in ("stable", "gradual") else 0.3

        return result

    async def analyze_batch(
        self,
        individuals: List[tuple[str, Optional[Dict[int, float]]]],
    ) -> Dict[str, DecayResult]:
        results = {}
        for oid, horizon_ic in individuals:
            results[oid] = await self.analyze(oid, horizon_ic)
        return results

    @staticmethod
    def get_horizons() -> List[int]:
        return list(HORIZONS)
