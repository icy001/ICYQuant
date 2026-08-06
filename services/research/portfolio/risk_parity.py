"""Risk Parity Optimizer — equal risk contribution portfolio.

Implements risk parity (equal risk contribution) optimization:
    RC_i = w_i * (Σ w)_i / sqrt(w^T Σ w)
    minimize: Σ_i (RC_i - 1/n)^2
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .optimizer import Optimizer, OptimizerType, OptimizeResult, OptimizeStatus

logger = logging.getLogger(__name__)


class RiskParityOptimizer(Optimizer):
    """Risk parity portfolio optimizer.

    Allocates weights so that each asset contributes equally
    to portfolio risk, reducing concentration risk.

    The optimization minimizes:
        Σ_i (RC_i - 1/n)^2
    where RC_i is the risk contribution of asset i.
    """

    def __init__(
        self,
        cov_matrix: Optional[Dict[str, Dict[str, float]]] = None,
        expected_returns: Optional[Dict[str, float]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        max_iterations: int = 500,
        tolerance: float = 1e-6,
        **kwargs: Any,
    ) -> None:
        super().__init__(cov_matrix, expected_returns, constraints, **kwargs)
        self._max_iterations = max_iterations
        self._tolerance = tolerance

    async def optimize(self) -> OptimizeResult:
        """Run risk parity optimization."""
        assets = self.assets
        if not assets:
            return OptimizeResult(
                weights={},
                optimizer_type=OptimizerType.RISK_PARITY,
                status=OptimizeStatus.INFEASIBLE,
                messages=["No assets in universe"],
            )

        n = len(assets)

        # Use inverse volatility as starting point
        weights = self._inverse_vol_weights(assets)
        target_rc = 1.0 / n

        for iteration in range(self._max_iterations):
            # Compute risk contributions
            portfolio_risk = max(self._compute_portfolio_risk(weights), 1e-10)
            portfolio_vol = portfolio_risk ** 0.5

            rc: Dict[str, float] = {}
            for i in assets:
                wi = weights[i]
                cov_sum = sum(
                    self._cov_matrix.get(i, {}).get(j, 0.0) * weights[j]
                    for j in assets
                )
                rc[i] = wi * cov_sum / portfolio_vol if portfolio_vol > 0 else 0.0

            # Normalize RC to percentages
            total_rc = sum(rc.values())
            if total_rc > 0:
                rc_pct = {a: rc[a] / total_rc for a in assets}
            else:
                rc_pct = {a: target_rc for a in assets}

            # Update weights: w_i *= target_rc / rc_pct_i
            new_weights: Dict[str, float] = {}
            for asset in assets:
                if rc_pct[asset] > 1e-10:
                    scale = target_rc / rc_pct[asset]
                else:
                    scale = 1.0
                new_weights[asset] = weights[asset] * scale

            # Normalize
            total = sum(new_weights.values())
            if total > 0:
                new_weights = {a: w / total for a, w in new_weights.items()}

            # Check convergence
            max_diff = max(
                abs(new_weights.get(a, 0.0) - weights.get(a, 0.0))
                for a in assets
            )
            weights = new_weights

            if max_diff < self._tolerance:
                break

        # Apply constraints
        weights = self._apply_constraints(weights)

        ret = self._compute_portfolio_return(weights)
        risk = self._compute_portfolio_risk(weights)
        sharpe = self._compute_sharpe(ret, risk)
        constraints_ok = self._check_constraints(weights)

        # Compute final RC
        portfolio_vol = max(risk, 1e-10) ** 0.5
        final_rc: Dict[str, float] = {}
        for i in assets:
            cov_sum = sum(
                self._cov_matrix.get(i, {}).get(j, 0.0) * weights[j]
                for j in assets
            )
            final_rc[i] = weights[i] * cov_sum / portfolio_vol if portfolio_vol > 0 else 0.0

        return OptimizeResult(
            weights=weights,
            optimizer_type=OptimizerType.RISK_PARITY,
            status=OptimizeStatus.OPTIMAL if constraints_ok else OptimizeStatus.FEASIBLE,
            expected_return=ret,
            expected_risk=risk,
            sharpe_ratio=sharpe,
            iterations=iteration + 1,
            objective_value=sum(
                (final_rc.get(a, 0) / max(sum(final_rc.values()), 1e-10) - target_rc) ** 2
                for a in assets
            ),
            constraints_satisfied=constraints_ok,
            metadata={
                "risk_contributions": final_rc,
                "target_rc": target_rc,
            },
        )

    def _inverse_vol_weights(self, assets: List[str]) -> Dict[str, float]:
        """Initialize weights proportional to inverse volatility."""
        inv_vol: Dict[str, float] = {}
        for asset in assets:
            var = self._cov_matrix.get(asset, {}).get(asset, 1.0)
            inv_vol[asset] = 1.0 / max(var ** 0.5, 1e-10)

        total = sum(inv_vol.values())
        if total > 0:
            return {a: inv_vol[a] / total for a in assets}
        else:
            n = len(assets)
            return {a: 1.0 / n for a in assets}

    def _apply_constraints(
        self, weights: Dict[str, float]
    ) -> Dict[str, float]:
        long_only = self._constraints.get("long_only", True)
        min_w = self._constraints.get("min_weight", 0.0)
        max_w = self._constraints.get("max_weight", 1.0)

        for asset in weights:
            if long_only and weights[asset] < 0:
                weights[asset] = 0.0
            weights[asset] = max(min_w, min(weights[asset], max_w))

        total = sum(weights.values())
        if total > 0:
            weights = {a: w / total for a, w in weights.items()}

        return weights
