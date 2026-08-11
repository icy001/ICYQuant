"""Risk Guard — Risk validation for evolved strategies before promotion."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RiskGuard:
    """Validates risk dimensions of candidate strategies."""

    def __init__(
        self,
        max_drawdown_pct: float = 20.0,
        max_leverage: float = 2.0,
        min_capacity_million: float = 10.0,
        max_correlation_to_existing: float = 0.70,
        max_concentration_pct: float = 25.0,
    ):
        self._max_drawdown = max_drawdown_pct
        self._max_leverage = max_leverage
        self._min_capacity = min_capacity_million
        self._max_correlation = max_correlation_to_existing
        self._max_concentration = max_concentration_pct

    async def validate(self, candidate_id: str, metrics: Dict[str, float]) -> Dict[str, Any]:
        """Validate risk profile of a candidate."""
        checks = {}

        # Max drawdown
        dd = metrics.get("max_drawdown_pct", 0)
        checks["max_drawdown"] = {
            "passed": dd <= self._max_drawdown,
            "value": dd,
            "threshold": self._max_drawdown,
        }

        # Leverage
        lev = metrics.get("leverage", 1.0)
        checks["leverage"] = {
            "passed": lev <= self._max_leverage,
            "value": lev,
            "threshold": self._max_leverage,
        }

        # Capacity
        cap = metrics.get("capacity_million", 0)
        checks["capacity"] = {
            "passed": cap >= self._min_capacity,
            "value": cap,
            "threshold": self._min_capacity,
        }

        # Concentration
        conc = metrics.get("max_position_pct", 0)
        checks["concentration"] = {
            "passed": conc <= self._max_concentration,
            "value": conc,
            "threshold": self._max_concentration,
        }

        all_passed = all(c["passed"] for c in checks.values())
        return {
            "candidate_id": candidate_id,
            "passed": all_passed,
            "checks": checks,
        }

    async def validate_batch(self, candidates: List[tuple[str, Dict[str, float]]]) -> Dict[str, Any]:
        results = {}
        for cid, metrics in candidates:
            results[cid] = await self.validate(cid, metrics)
        return results
