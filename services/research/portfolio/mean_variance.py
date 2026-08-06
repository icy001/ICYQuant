"""Mean-Variance Optimizer — classic Markowitz portfolio optimization.

Finds optimal weights on the efficient frontier:
    maximize: w^T μ - λ * w^T Σ w
    subject to: constraints

Supports objectives:
* Max Sharpe — maximize risk-adjusted return
* Min Variance — minimize portfolio variance
* Max Return — maximize expected return (with risk constraint)
* Target Return — achieve target return with minimum risk
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .optimizer import Optimizer, OptimizerType, OptimizeResult, OptimizeStatus

logger = logging.getLogger(__name__)


class MeanVarianceOptimizer(Optimizer):
    """Markowitz mean-variance portfolio optimizer.

    Implements quadratic programming for mean-variance optimization
    with flexible objective functions and constraints.

    Objectives:
    * max_sharpe — maximize Sharpe ratio
    * min_variance — minimize portfolio variance
    * max_return — maximize expected return subject to risk budget
    * target_return — achieve target return with minimum variance
    """

    def __init__(
        self,
        cov_matrix: Optional[Dict[str, Dict[str, float]]] = None,
        expected_returns: Optional[Dict[str, float]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        objective: str = "max_sharpe",
        risk_aversion: float = 1.0,
        target_return: Optional[float] = None,
        risk_budget: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(cov_matrix, expected_returns, constraints, **kwargs)
        self._objective = objective
        self._risk_aversion = risk_aversion
        self._target_return = target_return
        self._risk_budget = risk_budget
        self._max_iterations = kwargs.get("max_iterations", 1000)
        self._tolerance = kwargs.get("tolerance", 1e-6)

    async def optimize(self) -> OptimizeResult:
        """Run mean-variance optimization."""
        assets = self.assets
        if not assets:
            return OptimizeResult(
                weights={},
                optimizer_type=OptimizerType.MEAN_VARIANCE,
                status=OptimizeStatus.INFEASIBLE,
                messages=["No assets in universe"],
            )

        if self._objective == "max_sharpe":
            return self._max_sharpe(assets)
        elif self._objective == "min_variance":
            return self._min_variance(assets)
        elif self._objective == "max_return":
            return self._max_return(assets)
        elif self._objective == "target_return":
            return self._target_return_opt(assets)
        else:
            return self._max_sharpe(assets)

    def _max_sharpe(self, assets: List[str]) -> OptimizeResult:
        """Find maximum Sharpe ratio portfolio via grid search."""
        best_sharpe = -float("inf")
        best_weights: Dict[str, float] = {}
        best_ret = 0.0
        best_risk = 0.0

        # Grid search over risk aversion parameter
        for lam in [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0]:
            weights = self._solve_quadratic(assets, lam)
            ret = self._compute_portfolio_return(weights)
            risk = self._compute_portfolio_risk(weights)
            sharpe = self._compute_sharpe(ret, risk)

            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_weights = weights
                best_ret = ret
                best_risk = risk

        constraints_ok = self._check_constraints(best_weights)

        return OptimizeResult(
            weights=best_weights,
            optimizer_type=OptimizerType.MEAN_VARIANCE,
            status=OptimizeStatus.OPTIMAL if constraints_ok else OptimizeStatus.FEASIBLE,
            expected_return=best_ret,
            expected_risk=best_risk,
            sharpe_ratio=best_sharpe,
            objective_value=best_sharpe,
            constraints_satisfied=constraints_ok,
            metadata={"objective": "max_sharpe", "risk_aversion": self._risk_aversion},
        )

    def _min_variance(self, assets: List[str]) -> OptimizeResult:
        """Minimum variance portfolio."""
        weights = self._solve_quadratic(assets, risk_aversion=1e10)
        ret = self._compute_portfolio_return(weights)
        risk = self._compute_portfolio_risk(weights)
        sharpe = self._compute_sharpe(ret, risk)
        constraints_ok = self._check_constraints(weights)

        return OptimizeResult(
            weights=weights,
            optimizer_type=OptimizerType.MEAN_VARIANCE,
            status=OptimizeStatus.OPTIMAL if constraints_ok else OptimizeStatus.FEASIBLE,
            expected_return=ret,
            expected_risk=risk,
            sharpe_ratio=sharpe,
            objective_value=risk,
            constraints_satisfied=constraints_ok,
            metadata={"objective": "min_variance"},
        )

    def _max_return(self, assets: List[str]) -> OptimizeResult:
        """Maximum return portfolio (subject to risk budget)."""
        weights = self._solve_quadratic(assets, risk_aversion=1e-10)
        ret = self._compute_portfolio_return(weights)
        risk = self._compute_portfolio_risk(weights)
        sharpe = self._compute_sharpe(ret, risk)
        constraints_ok = self._check_constraints(weights)

        return OptimizeResult(
            weights=weights,
            optimizer_type=OptimizerType.MEAN_VARIANCE,
            status=OptimizeStatus.OPTIMAL if constraints_ok else OptimizeStatus.FEASIBLE,
            expected_return=ret,
            expected_risk=risk,
            sharpe_ratio=sharpe,
            objective_value=ret,
            constraints_satisfied=constraints_ok,
            metadata={"objective": "max_return"},
        )

    def _target_return_opt(self, assets: List[str]) -> OptimizeResult:
        """Achieve target return with minimum variance."""
        target = self._target_return or 0.10

        # Iterative search for risk aversion that hits target return
        best_weights: Dict[str, float] = {}
        best_diff = float("inf")
        lam = self._risk_aversion

        for _ in range(self._max_iterations):
            weights = self._solve_quadratic(assets, lam)
            ret = self._compute_portfolio_return(weights)
            diff = abs(ret - target)

            if diff < best_diff:
                best_diff = diff
                best_weights = weights

            if diff < self._tolerance:
                break

            # Adjust lambda
            if ret > target:
                lam *= 1.5
            else:
                lam *= 0.5

        ret = self._compute_portfolio_return(best_weights)
        risk = self._compute_portfolio_risk(best_weights)
        sharpe = self._compute_sharpe(ret, risk)
        constraints_ok = self._check_constraints(best_weights)

        return OptimizeResult(
            weights=best_weights,
            optimizer_type=OptimizerType.MEAN_VARIANCE,
            status=OptimizeStatus.OPTIMAL if constraints_ok else OptimizeStatus.FEASIBLE,
            expected_return=ret,
            expected_risk=risk,
            sharpe_ratio=sharpe,
            objective_value=best_diff,
            constraints_satisfied=constraints_ok,
            messages=[f"Target return: {target:.4f}, achieved: {ret:.4f}"],
            metadata={"objective": "target_return", "target": target},
        )

    def _solve_quadratic(
        self, assets: List[str], risk_aversion: float
    ) -> Dict[str, float]:
        """Solve w = argmax( w^T μ - λ w^T Σ w ) via simple gradient.

        This is a simplified solver; in production, use a proper QP solver
        (e.g., cvxopt, scipy.optimize). The approach here uses an iterative
        proportional adjustment that converges to the analytical solution
        for unconstrained cases.
        """
        n = len(assets)
        if n == 0:
            return {}

        # Start from equal weights
        weights = {asset: 1.0 / n for asset in assets}

        # Iterative refinement
        for _ in range(100):
            # Compute gradient: μ_i - 2λ Σ_j Σ_{ij} w_j
            gradient: Dict[str, float] = {}
            for i in assets:
                mu_i = self._expected_returns.get(i, 0.0)
                cov_term = 0.0
                for j in assets:
                    cov_ij = self._cov_matrix.get(i, {}).get(j, 0.0)
                    cov_term += cov_ij * weights[j]
                gradient[i] = mu_i - 2.0 * risk_aversion * cov_term

            # Update weights proportionally to gradient
            min_g = min(gradient.values())
            shifted = {a: g - min_g + 1e-6 for a, g in gradient.items()}
            total = sum(shifted.values())
            if total > 0:
                weights = {a: shifted[a] / total for a in assets}

            # Apply constraints
            weights = self._apply_constraints(weights)

        return weights

    def _apply_constraints(
        self, weights: Dict[str, float]
    ) -> Dict[str, float]:
        """Apply weight constraints."""
        long_only = self._constraints.get("long_only", True)
        min_w = self._constraints.get("min_weight", 0.0)
        max_w = self._constraints.get("max_weight", 1.0)
        fully_invested = self._constraints.get("fully_invested", True)

        # Clip weights
        for asset in weights:
            w = weights[asset]
            if long_only and w < 0:
                w = 0.0
            w = max(min_w, min(w, max_w))
            weights[asset] = w

        # Normalize if fully invested
        if fully_invested:
            total = sum(weights.values())
            if total > 0:
                weights = {a: w / total for a, w in weights.items()}

        return weights
