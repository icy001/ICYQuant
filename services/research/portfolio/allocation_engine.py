"""Allocation Engine — unified weight allocation for portfolio construction.

Supports allocation methods:
* Equal Weight
* Risk Weight (inverse volatility)
* Factor Weight
* Score Weight (rank-based)
* Custom Allocation
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AllocationMethod(str, Enum):
    """Predefined allocation methods."""

    EQUAL_WEIGHT = "equal_weight"
    RISK_WEIGHT = "risk_weight"
    FACTOR_WEIGHT = "factor_weight"
    SCORE_WEIGHT = "score_weight"
    CUSTOM = "custom"


@dataclass
class AllocationResult:
    """Result of weight allocation."""

    weights: Dict[str, float]
    method: AllocationMethod = AllocationMethod.EQUAL_WEIGHT
    total_weight: float = 0.0
    num_assets: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "weights": self.weights,
            "method": self.method.value,
            "total_weight": self.total_weight,
            "num_assets": self.num_assets,
            "metadata": self.metadata,
        }


class AllocationEngine:
    """Unified weight allocation for portfolio construction.

    Transforms candidate universes into weighted portfolios
    using configurable allocation methods.
    """

    def __init__(self) -> None:
        pass

    async def allocate(
        self,
        candidates: Any,  # BuildResult or similar
        method: str = "equal_weight",
        scores: Optional[Dict[str, float]] = None,
        volatilities: Optional[Dict[str, float]] = None,
        factor_exposures: Optional[Dict[str, Dict[str, float]]] = None,
        target_weights: Optional[Dict[str, float]] = None,
        **kwargs: Any,
    ) -> AllocationResult:
        """Allocate weights to portfolio candidates."""

        # Extract universe from candidates
        universe = self._extract_universe(candidates)

        alloc_method = AllocationMethod(method)

        if alloc_method == AllocationMethod.EQUAL_WEIGHT:
            return self._equal_weight(universe)
        elif alloc_method == AllocationMethod.RISK_WEIGHT:
            return self._risk_weight(universe, volatilities)
        elif alloc_method == AllocationMethod.SCORE_WEIGHT:
            return self._score_weight(universe, scores)
        elif alloc_method == AllocationMethod.FACTOR_WEIGHT:
            return self._factor_weight(universe, factor_exposures)
        elif alloc_method == AllocationMethod.CUSTOM:
            return self._custom_weight(universe, target_weights)
        else:
            return self._equal_weight(universe)

    def _extract_universe(self, candidates: Any) -> List[str]:
        """Extract universe list from various input types."""
        if isinstance(candidates, list):
            return candidates
        if hasattr(candidates, "universe"):
            return candidates.universe
        if isinstance(candidates, dict):
            return list(candidates.get("universe", []))
        return []

    def _equal_weight(self, universe: List[str]) -> AllocationResult:
        if not universe:
            return AllocationResult(
                weights={}, total_weight=0.0, num_assets=0
            )
        n = len(universe)
        weight = 1.0 / n
        weights = {asset: weight for asset in universe}
        return AllocationResult(
            weights=weights,
            method=AllocationMethod.EQUAL_WEIGHT,
            total_weight=1.0,
            num_assets=n,
        )

    def _risk_weight(
        self,
        universe: List[str],
        volatilities: Optional[Dict[str, float]],
    ) -> AllocationResult:
        """Inverse volatility weighting."""
        if not universe:
            return AllocationResult(weights={}, total_weight=0.0, num_assets=0)

        if volatilities is None:
            return self._equal_weight(universe)

        inv_vol = {}
        for asset in universe:
            vol = volatilities.get(asset, 1.0)
            if vol <= 0:
                inv_vol[asset] = 1.0
            else:
                inv_vol[asset] = 1.0 / vol

        total_inv = sum(inv_vol.values())
        if total_inv == 0:
            return self._equal_weight(universe)

        weights = {asset: inv_vol[asset] / total_inv for asset in universe}
        return AllocationResult(
            weights=weights,
            method=AllocationMethod.RISK_WEIGHT,
            total_weight=sum(weights.values()),
            num_assets=len(universe),
        )

    def _score_weight(
        self,
        universe: List[str],
        scores: Optional[Dict[str, float]],
    ) -> AllocationResult:
        """Score-based weighting (higher score → higher weight)."""
        if not universe or not scores:
            return self._equal_weight(universe)

        raw_scores = {asset: max(scores.get(asset, 0.0), 0.0) for asset in universe}
        total_score = sum(raw_scores.values())
        if total_score == 0:
            return self._equal_weight(universe)

        weights = {asset: raw_scores[asset] / total_score for asset in universe}
        return AllocationResult(
            weights=weights,
            method=AllocationMethod.SCORE_WEIGHT,
            total_weight=sum(weights.values()),
            num_assets=len(universe),
        )

    def _factor_weight(
        self,
        universe: List[str],
        factor_exposures: Optional[Dict[str, Dict[str, float]]],
    ) -> AllocationResult:
        """Factor-based weighting."""
        if not universe or not factor_exposures:
            return self._equal_weight(universe)

        # Sum factor exposures per asset
        exposure_sum = {}
        for asset in universe:
            total = sum(
                factor_exposures.get(asset, {}).values()
            )
            exposure_sum[asset] = max(total, 0.01)

        total = sum(exposure_sum.values())
        if total == 0:
            return self._equal_weight(universe)

        weights = {asset: exposure_sum[asset] / total for asset in universe}
        return AllocationResult(
            weights=weights,
            method=AllocationMethod.FACTOR_WEIGHT,
            total_weight=sum(weights.values()),
            num_assets=len(universe),
        )

    def _custom_weight(
        self,
        universe: List[str],
        target_weights: Optional[Dict[str, float]],
    ) -> AllocationResult:
        """Use pre-specified custom weights."""
        if not target_weights:
            return self._equal_weight(universe)

        weights = {
            asset: target_weights.get(asset, 0.0)
            for asset in universe
        }
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return AllocationResult(
            weights=weights,
            method=AllocationMethod.CUSTOM,
            total_weight=sum(weights.values()),
            num_assets=len(universe),
        )
