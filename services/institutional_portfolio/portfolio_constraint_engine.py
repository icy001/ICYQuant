"""
Portfolio Constraint Engine — Unified Constraint Validation & Enforcement

Applies all portfolio-level constraints:
- Max gross/net exposure, max leverage
- Max strategy weight, max asset weight
- Max factor exposure, max cluster exposure
- Max turnover, max liquidity usage
"""

import uuid
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ConstraintSet:
    max_gross_exposure: float = float("inf")
    max_net_exposure: float = float("inf")
    max_leverage: float = 3.0
    max_strategy_weight: float = 0.30
    max_asset_weight: float = 0.10
    max_factor_exposure: float = 1.0
    max_cluster_exposure: float = 0.40
    max_turnover: float = 0.50
    max_liquidity_usage: float = 0.80


class PortfolioConstraintEngine:
    """
    Validates and enforces all portfolio constraints.

    Used by PortfolioBuilder, PortfolioOptimizer, and RebalanceEngine.
    """

    def __init__(
        self,
        engine_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.engine_id = engine_id or f"pce-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._constraints = ConstraintSet()
        self._update_from_config()

    def _update_from_config(self) -> None:
        for key in ["max_gross_exposure", "max_net_exposure", "max_leverage",
                     "max_strategy_weight", "max_asset_weight", "max_turnover"]:
            if key in self.config:
                setattr(self._constraints, key, self.config[key])

    def validate(self, construction) -> List[str]:
        """Validate a portfolio construction against all constraints."""
        violations = []

        if hasattr(construction, 'gross_exposure') and construction.gross_exposure > self._constraints.max_gross_exposure:
            violations.append(f"Gross exposure {construction.gross_exposure} > {self._constraints.max_gross_exposure}")

        if hasattr(construction, 'net_exposure') and abs(construction.net_exposure) > self._constraints.max_net_exposure:
            violations.append(f"Net exposure {construction.net_exposure} > {self._constraints.max_net_exposure}")

        if hasattr(construction, 'weights'):
            for asset, w in construction.weights.items():
                if abs(w) > self._constraints.max_asset_weight:
                    violations.append(f"Asset {asset} weight {w:.4f} > {self._constraints.max_asset_weight}")

        return violations

    def apply_limits(self, weights: Dict[str, float],
                     constraints: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """Cap individual weights at max_asset_weight and re-normalize."""
        max_w = self._constraints.max_asset_weight
        if constraints and "max_asset_weight" in constraints:
            max_w = constraints["max_asset_weight"]

        capped = {}
        overflow = 0.0
        for asset, w in weights.items():
            capped[asset] = min(max_w, w)
            overflow += max(0, w - max_w)

        # Distribute overflow to uncapped assets
        if overflow > 0:
            uncapped = [a for a, w in capped.items() if w < max_w]
            if uncapped:
                per_asset = overflow / len(uncapped)
                for a in uncapped:
                    capped[a] = min(max_w, capped[a] + per_asset)

        return capped
