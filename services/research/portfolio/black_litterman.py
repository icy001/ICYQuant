"""Black-Litterman Optimizer — blend market equilibrium with investor views.

Combines market-implied equilibrium returns with subjective investor
views to produce posterior expected returns, then optimizes.

Formula:
    Π = λ Σ w_mkt          (implied equilibrium returns)
    E[R] = [(τΣ)^-1 + P^T Ω^-1 P]^-1 [(τΣ)^-1 Π + P^T Ω^-1 Q]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .optimizer import Optimizer, OptimizerType, OptimizeResult, OptimizeStatus

logger = logging.getLogger(__name__)


@dataclass
class BLView:
    """A single Black-Litterman investor view.

    Views can be:
    * Absolute: "Asset A will return 10%"
    * Relative: "Asset A will outperform Asset B by 3%"
    """

    assets: List[str]
    value: float  # expected return or spread
    confidence: float = 0.5  # 0-1, higher = more confident
    view_type: str = "absolute"  # "absolute" or "relative"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assets": self.assets,
            "value": self.value,
            "confidence": self.confidence,
            "view_type": self.view_type,
        }


class BlackLittermanOptimizer(Optimizer):
    """Black-Litterman portfolio optimizer.

    Fuses market equilibrium returns with investor views to
    produce robust posterior expected returns, avoiding the
    sensitivity issues of pure mean-variance optimization.
    """

    def __init__(
        self,
        cov_matrix: Optional[Dict[str, Dict[str, float]]] = None,
        expected_returns: Optional[Dict[str, float]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        views: Optional[List[BLView]] = None,
        market_weights: Optional[Dict[str, float]] = None,
        risk_aversion: float = 2.5,
        tau: float = 0.05,
        **kwargs: Any,
    ) -> None:
        super().__init__(cov_matrix, expected_returns, constraints, **kwargs)
        self._views = views or []
        self._market_weights = market_weights or {}
        self._risk_aversion = risk_aversion
        self._tau = tau  # uncertainty in prior

    async def optimize(self) -> OptimizeResult:
        """Run Black-Litterman optimization."""
        assets = self.assets
        if not assets:
            return OptimizeResult(
                weights={},
                optimizer_type=OptimizerType.BLACK_LITTERMAN,
                status=OptimizeStatus.INFEASIBLE,
                messages=["No assets in universe"],
            )

        # Step 1: Compute implied equilibrium returns
        pi = self._implied_equilibrium(assets)

        # Step 2: Apply views → posterior returns
        posterior_returns = self._apply_views(assets, pi)

        # Step 3: Mean-variance optimization with posterior returns
        # Use the mean-variance solver approach
        weights = self._solve_bl(assets, posterior_returns)

        # Apply constraints
        weights = self._apply_constraints(weights)

        ret = sum(
            weights.get(a, 0.0) * posterior_returns.get(a, 0.0)
            for a in assets
        )
        risk = self._compute_portfolio_risk(weights)
        sharpe = self._compute_sharpe(ret, risk)
        constraints_ok = self._check_constraints(weights)

        return OptimizeResult(
            weights=weights,
            optimizer_type=OptimizerType.BLACK_LITTERMAN,
            status=OptimizeStatus.OPTIMAL if constraints_ok else OptimizeStatus.FEASIBLE,
            expected_return=ret,
            expected_risk=risk,
            sharpe_ratio=sharpe,
            constraints_satisfied=constraints_ok,
            metadata={
                "prior_returns": pi,
                "posterior_returns": posterior_returns,
                "num_views": len(self._views),
                "tau": self._tau,
            },
        )

    def _implied_equilibrium(self, assets: List[str]) -> Dict[str, float]:
        """Compute implied equilibrium returns: Π = λ Σ w_mkt."""
        if not self._market_weights:
            # Equal weight as default market portfolio
            n = len(assets)
            self._market_weights = {a: 1.0 / n for a in assets}

        pi: Dict[str, float] = {}
        for i in assets:
            cov_sum = 0.0
            for j in assets:
                cov_ij = self._cov_matrix.get(i, {}).get(j, 0.0)
                cov_sum += cov_ij * self._market_weights.get(j, 0.0)
            pi[i] = self._risk_aversion * cov_sum

        return pi

    def _apply_views(
        self, assets: List[str], pi: Dict[str, float]
    ) -> Dict[str, float]:
        """Apply investor views to get posterior returns.

        E[R] = [(τΣ)^-1 + P^T Ω^-1 P]^-1 [(τΣ)^-1 Π + P^T Ω^-1 Q]
        """
        if not self._views:
            return dict(pi)

        n = len(assets)
        k = len(self._views)
        asset_index = {a: i for i, a in enumerate(assets)}

        # Build P matrix (k × n) and Q vector
        P: List[List[float]] = [[0.0] * n for _ in range(k)]
        Q: List[float] = [0.0] * k
        omega_diag: List[float] = [0.0] * k

        for v_idx, view in enumerate(self._views):
            if view.view_type == "absolute":
                for asset in view.assets:
                    if asset in asset_index:
                        P[v_idx][asset_index[asset]] = 1.0
                Q[v_idx] = view.value
            else:  # relative
                if len(view.assets) >= 2:
                    a1, a2 = view.assets[0], view.assets[1]
                    if a1 in asset_index:
                        P[v_idx][asset_index[a1]] = 1.0
                    if a2 in asset_index:
                        P[v_idx][asset_index[a2]] = -1.0
                Q[v_idx] = view.value

            # Ω diagonal: variance of view error
            # Higher confidence → lower variance
            confidence = max(view.confidence, 0.01)
            omega_diag[v_idx] = (1.0 / confidence - 1.0) * self._tau

        # Simplified computation: weighted blend of prior and views
        posterior = dict(pi)
        for v_idx, view in enumerate(self._views):
            weight = 1.0 / (1.0 + omega_diag[v_idx])
            if view.view_type == "absolute":
                for asset in view.assets:
                    if asset in posterior:
                        posterior[asset] = (
                            (1 - weight) * pi.get(asset, 0.0)
                            + weight * view.value
                        )
            else:
                if len(view.assets) >= 2:
                    a1, a2 = view.assets[0], view.assets[1]
                    spread = view.value
                    if a1 in posterior and a2 in posterior:
                        # Adjust both assets to reflect the spread
                        prior_spread = pi.get(a1, 0.0) - pi.get(a2, 0.0)
                        adj_spread = (1 - weight) * prior_spread + weight * spread
                        avg = (pi.get(a1, 0.0) + pi.get(a2, 0.0)) / 2
                        posterior[a1] = avg + adj_spread / 2
                        posterior[a2] = avg - adj_spread / 2

        return posterior

    def _solve_bl(
        self, assets: List[str], posterior_returns: Dict[str, float]
    ) -> Dict[str, float]:
        """Solve for optimal weights given posterior returns."""
        n = len(assets)
        weights = {a: 1.0 / n for a in assets}

        # Iterative refinement toward max Sharpe
        for _ in range(100):
            gradient: Dict[str, float] = {}
            for i in assets:
                mu_i = posterior_returns.get(i, 0.0)
                cov_term = 0.0
                for j in assets:
                    cov_ij = self._cov_matrix.get(i, {}).get(j, 0.0)
                    cov_term += cov_ij * weights[j]
                gradient[i] = mu_i - self._risk_aversion * cov_term

            min_g = min(gradient.values())
            shifted = {a: max(g - min_g + 1e-6, 0.0) for a, g in gradient.items()}
            total = sum(shifted.values())
            if total > 0:
                weights = {a: shifted[a] / total for a in assets}

        return weights

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
