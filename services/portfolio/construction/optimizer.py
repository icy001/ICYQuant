"""
Portfolio Optimizer

Implements portfolio optimization methods:
- Mean-Variance Optimization (maximize return - risk penalty)
- Risk Parity (equalize risk contributions)
- Equal Weight baseline
- Max Sharpe tangent portfolio
- Min Variance portfolio
"""

from __future__ import annotations

import math
import time
from typing import Dict, List, Optional, Tuple

from .models import (
    AllocationReason,
    OptimizationMethod,
    OptimizationMetrics,
    OptimizationResult,
    PortfolioConstraints,
    RiskBudgetAllocation,
    StrategyAllocation,
    StrategySnapshot,
)


class PortfolioOptimizer:
    """Base optimizer with shared utilities."""

    def __init__(self, risk_aversion: float = 1.0):
        self.risk_aversion = risk_aversion

    def _build_covariance_matrix(
        self,
        volatilities: Dict[str, float],
        correlations: Dict[str, Dict[str, float]],
    ) -> Dict[str, Dict[str, float]]:
        """Build covariance matrix from volatilities and correlations."""
        strategies = list(volatilities.keys())
        cov = {s: {} for s in strategies}

        for si in strategies:
            for sj in strategies:
                if si == sj:
                    cov[si][sj] = volatilities[si] ** 2
                else:
                    rho = correlations.get(si, {}).get(sj, 0.3)  # default correlation
                    cov[si][sj] = rho * volatilities[si] * volatilities[sj]

        return cov

    def _portfolio_variance(
        self,
        weights: Dict[str, float],
        cov: Dict[str, Dict[str, float]],
    ) -> float:
        """Calculate portfolio variance w^T * Sigma * w."""
        strategies = list(weights.keys())
        var = 0.0
        for si in strategies:
            for sj in strategies:
                var += weights[si] * weights[sj] * cov.get(si, {}).get(sj, 0.0)
        return var

    def _portfolio_return(self, weights: Dict[str, float], returns: Dict[str, float]) -> float:
        """Calculate portfolio expected return."""
        return sum(weights[s] * returns.get(s, 0.0) for s in weights)

    def _sharpe_ratio(
        self,
        weights: Dict[str, float],
        returns: Dict[str, float],
        cov: Dict[str, Dict[str, float]],
        risk_free_rate: float = 0.0,
    ) -> float:
        """Calculate Sharpe ratio for given weights."""
        port_ret = self._portfolio_return(weights, returns)
        port_var = self._portfolio_variance(weights, cov)
        port_vol = math.sqrt(max(port_var, 1e-12))
        if port_vol == 0:
            return 0.0
        return (port_ret - risk_free_rate) / port_vol

    def _effective_n(self, weights: Dict[str, float]) -> float:
        """Effective number of strategies (diversification measure)."""
        w = [v for v in weights.values() if v > 0]
        if not w:
            return 0.0
        sum_sq = sum(x * x for x in w)
        if sum_sq == 0:
            return 0.0
        return 1.0 / sum_sq

    def _herfindahl(self, weights: Dict[str, float]) -> float:
        """Herfindahl-Hirschman Index for concentration."""
        w = [v for v in weights.values() if v > 0]
        return sum(x * x for x in w)

    def _marginal_risk_contributions(
        self,
        weights: Dict[str, float],
        cov: Dict[str, Dict[str, float]],
    ) -> Dict[str, float]:
        """Calculate marginal risk contributions for each strategy."""
        port_var = self._portfolio_variance(weights, cov)
        port_vol = math.sqrt(max(port_var, 1e-12))
        if port_vol == 0:
            return {s: 0.0 for s in weights}

        mrc = {}
        strategies = list(weights.keys())
        for si in strategies:
            marginal = 0.0
            for sj in strategies:
                marginal += weights[sj] * cov.get(si, {}).get(sj, 0.0)
            mrc[si] = marginal / port_vol
        return mrc

    def _total_risk_contributions(
        self,
        weights: Dict[str, float],
        cov: Dict[str, Dict[str, float]],
    ) -> Dict[str, float]:
        """Calculate total risk contributions (weight * MRC)."""
        mrc = self._marginal_risk_contributions(weights, cov)
        return {s: weights[s] * mrc[s] for s in weights}

    def _calculate_turnover(
        self,
        new_weights: Dict[str, float],
        old_weights: Dict[str, float],
    ) -> float:
        """Calculate two-way turnover."""
        all_keys = set(new_weights.keys()) | set(old_weights.keys())
        turnover = 0.0
        for k in all_keys:
            turnover += abs(new_weights.get(k, 0.0) - old_weights.get(k, 0.0))
        return turnover / 2.0  # two-way

    def _build_metrics(
        self,
        method: OptimizationMethod,
        weights: Dict[str, float],
        returns: Dict[str, float],
        cov: Dict[str, Dict[str, float]],
        old_weights: Optional[Dict[str, float]] = None,
        risk_free_rate: float = 0.0,
        iterations: int = 0,
        converged: bool = True,
        elapsed_ms: float = 0.0,
    ) -> OptimizationMetrics:
        """Build OptimizationMetrics from results."""
        port_ret = self._portfolio_return(weights, returns)
        port_var = self._portfolio_variance(weights, cov)
        port_vol = math.sqrt(max(port_var, 1e-12))
        sharpe = self._sharpe_ratio(weights, returns, cov, risk_free_rate)
        div_ratio = 0.0
        if port_vol > 0:
            w = [weights[s] for s in weights]
            vol_w = [math.sqrt(max(cov.get(s, {}).get(s, 0.0), 1e-12)) for s in weights]
            avg_vol = sum(w[i] * vol_w[i] for i in range(len(w))) if w else 0
            if avg_vol > 0:
                div_ratio = avg_vol / port_vol

        turnover = 0.0
        if old_weights:
            turnover = self._calculate_turnover(weights, old_weights)

        return OptimizationMetrics(
            method=method,
            expected_return=port_ret,
            expected_volatility=port_vol,
            sharpe_ratio=sharpe,
            diversification_ratio=div_ratio,
            effective_n=self._effective_n(weights),
            herfindahl_index=self._herfindahl(weights),
            turnover=turnover,
            iterations=iterations,
            converged=converged,
            optimization_time_ms=elapsed_ms,
        )

    def _enforce_weight_constraints(
        self,
        weights: Dict[str, float],
        constraints: Optional[PortfolioConstraints],
    ) -> Dict[str, float]:
        """Clamp weights to satisfy constraints."""
        if constraints is None:
            return weights

        result = dict(weights)

        # Apply per-strategy constraints
        for sid, wc in constraints.weight_constraints.items():
            if sid in result:
                result[sid] = max(wc.min_weight, min(result[sid], wc.max_weight))
                if wc.step_size > 0:
                    result[sid] = round(result[sid] / wc.step_size) * wc.step_size

        # Apply global max single strategy constraint
        for sid in result:
            result[sid] = min(result[sid], constraints.max_single_strategy_weight)
            result[sid] = max(result[sid], constraints.min_single_strategy_weight)

        # Normalize to sum to max_total_weight
        # Redistribute excess from clamped weights to unconstrained strategies
        total = sum(result.values())
        if total > 0 and abs(total - constraints.max_total_weight) > 1e-10:
            # Identify constrained vs unconstrained strategies
            constrained = set()
            for sid in result:
                wc = constraints.weight_constraints.get(sid)
                if wc and (result[sid] <= wc.min_weight + 1e-10 or result[sid] >= wc.max_weight - 1e-10):
                    constrained.add(sid)
                elif result[sid] >= constraints.max_single_strategy_weight - 1e-10:
                    constrained.add(sid)

            unconstrained = [s for s in result if s not in constrained]

            if total < constraints.max_total_weight and unconstrained:
                # Need to scale up: distribute to unconstrained strategies
                deficit = constraints.max_total_weight - total
                unconstrained_total = sum(result[s] for s in unconstrained)
                if unconstrained_total > 0:
                    for s in unconstrained:
                        result[s] += deficit * (result[s] / unconstrained_total)
                        result[s] = min(result[s], constraints.max_single_strategy_weight)
            elif total > constraints.max_total_weight:
                # Need to scale down: reduce all proportionally
                scale = constraints.max_total_weight / total
                result = {s: w * scale for s, w in result.items()}

        return result


class MeanVarianceOptimizer(PortfolioOptimizer):
    """
    Mean-Variance Optimization.

    Maximize: E(Rp) - lambda * sigma^2(p)

    Uses a grid search approach to find optimal weights
    that maximize the utility function subject to constraints.
    """

    def __init__(
        self,
        risk_aversion: float = 1.0,
        grid_points: int = 20,
        max_iterations: int = 100,
    ):
        super().__init__(risk_aversion)
        self.grid_points = grid_points
        self.max_iterations = max_iterations

    def optimize(
        self,
        snapshots: Dict[str, StrategySnapshot],
        constraints: Optional[PortfolioConstraints] = None,
        old_weights: Optional[Dict[str, float]] = None,
        risk_free_rate: float = 0.0,
    ) -> OptimizationResult:
        """Run Mean-Variance optimization."""
        start_time = time.time()
        strategy_ids = list(snapshots.keys())
        n = len(strategy_ids)

        if n == 0:
            return OptimizationResult(
                portfolio_id="",
                method=OptimizationMethod.MEAN_VARIANCE,
                metrics=OptimizationMetrics(method=OptimizationMethod.MEAN_VARIANCE),
                status="error",
                message="No strategies provided",
            )

        # Extract returns and build covariance
        returns = {sid: snapshots[sid].expected_return for sid in strategy_ids}
        volatilities = {sid: snapshots[sid].expected_volatility for sid in strategy_ids}

        # Build correlation matrix from tracking error / volatilities
        correlations = {}
        for si in strategy_ids:
            correlations[si] = {}
            for sj in strategy_ids:
                if si == sj:
                    correlations[si][sj] = 1.0
                else:
                    correlations[si][sj] = snapshots[si].correlation_to_portfolio

        cov = self._build_covariance_matrix(volatilities, correlations)

        # Grid search for optimal weights
        best_weights = None
        best_utility = float("-inf")
        iterations = 0
        converged = False

        # Start from equal weights
        weights = {sid: 1.0 / n for sid in strategy_ids}

        for iteration in range(self.max_iterations):
            iterations += 1

            # Enforce constraints
            weights = self._enforce_weight_constraints(weights, constraints)

            # Calculate utility
            port_ret = self._portfolio_return(weights, returns)
            port_var = self._portfolio_variance(weights, cov)
            utility = port_ret - self.risk_aversion * port_var

            if utility > best_utility:
                best_utility = utility
                best_weights = dict(weights)
                if iteration > 0:
                    converged = True

            # Gradient-based update
            mrc = self._marginal_risk_contributions(weights, cov)
            grad = {}
            for sid in strategy_ids:
                grad[sid] = returns[sid] - 2 * self.risk_aversion * mrc[sid]

            # Step in gradient direction
            step_size = 1.0 / (iteration + 2)
            for sid in strategy_ids:
                weights[sid] += step_size * grad[sid]
                weights[sid] = max(0.0, weights[sid])

            # Normalize
            total = sum(weights.values())
            if total > 0:
                weights = {s: w / total for s, w in weights.items()}

            # Check convergence
            if converged and iteration > 10:
                break

        if best_weights is None:
            best_weights = {sid: 1.0 / n for sid in strategy_ids}

        elapsed_ms = (time.time() - start_time) * 1000
        metrics = self._build_metrics(
            OptimizationMethod.MEAN_VARIANCE,
            best_weights,
            returns,
            cov,
            old_weights,
            risk_free_rate,
            iterations,
            converged,
            elapsed_ms,
        )

        return OptimizationResult(
            portfolio_id="",
            method=OptimizationMethod.MEAN_VARIANCE,
            weights=best_weights,
            metrics=metrics,
            iterations=iterations,
        )


class RiskParityOptimizer(PortfolioOptimizer):
    """
    Risk Parity Optimization.

    Equalizes risk contributions across strategies:
    RC_i = RC_j for all i, j

    Uses iterative method to find weights where each strategy
    contributes equally to total portfolio risk.
    """

    def __init__(self, max_iterations: int = 50, tolerance: float = 1e-6):
        super().__init__()
        self.max_iterations = max_iterations
        self.tolerance = tolerance

    def optimize(
        self,
        snapshots: Dict[str, StrategySnapshot],
        constraints: Optional[PortfolioConstraints] = None,
        old_weights: Optional[Dict[str, float]] = None,
        risk_free_rate: float = 0.0,
    ) -> OptimizationResult:
        """Run Risk Parity optimization."""
        start_time = time.time()
        strategy_ids = list(snapshots.keys())
        n = len(strategy_ids)

        if n == 0:
            return OptimizationResult(
                portfolio_id="",
                method=OptimizationMethod.RISK_PARITY,
                metrics=OptimizationMetrics(method=OptimizationMethod.RISK_PARITY),
                status="error",
                message="No strategies provided",
            )

        returns = {sid: snapshots[sid].expected_return for sid in strategy_ids}
        volatilities = {sid: snapshots[sid].expected_volatility for sid in strategy_ids}
        correlations = {}
        for si in strategy_ids:
            correlations[si] = {}
            for sj in strategy_ids:
                if si == sj:
                    correlations[si][sj] = 1.0
                else:
                    correlations[si][sj] = snapshots[si].correlation_to_portfolio

        cov = self._build_covariance_matrix(volatilities, correlations)

        # Initialize with inverse-vol weights
        inv_vol = {}
        for sid in strategy_ids:
            vol = volatilities.get(sid, 0.01)
            inv_vol[sid] = 1.0 / max(vol, 0.001)
        total_inv = sum(inv_vol.values())
        weights = {sid: inv_vol[sid] / total_inv for sid in strategy_ids}

        converged = False
        for iteration in range(self.max_iterations):
            trc = self._total_risk_contributions(weights, cov)
            port_var = self._portfolio_variance(weights, cov)
            port_vol = math.sqrt(max(port_var, 1e-12))

            if port_vol == 0:
                break

            # Target: equal risk contribution
            target_rc = port_vol / n

            # Update weights based on risk contribution ratio
            max_diff = 0.0
            new_weights = {}
            for sid in strategy_ids:
                rc = trc.get(sid, 0.0)
                if rc > 0:
                    new_weights[sid] = weights[sid] * (target_rc / rc) ** 0.5
                else:
                    new_weights[sid] = weights[sid]
                diff = abs(rc - target_rc) / max(port_vol / n, 1e-12)
                max_diff = max(max_diff, diff)

            # Normalize
            total = sum(new_weights.values())
            if total > 0:
                weights = {s: w / total for s, w in new_weights.items()}

            if max_diff < self.tolerance:
                converged = True
                break

        # Enforce constraints
        weights = self._enforce_weight_constraints(weights, constraints)

        elapsed_ms = (time.time() - start_time) * 1000
        metrics = self._build_metrics(
            OptimizationMethod.RISK_PARITY,
            weights,
            returns,
            cov,
            old_weights,
            risk_free_rate,
            iterations=iteration + 1,
            converged=converged,
            elapsed_ms=elapsed_ms,
        )

        return OptimizationResult(
            portfolio_id="",
            method=OptimizationMethod.RISK_PARITY,
            weights=weights,
            metrics=metrics,
            iterations=iteration + 1,
        )


class MaxSharpeOptimizer(PortfolioOptimizer):
    """Maximum Sharpe Ratio optimizer."""

    def __init__(self, grid_points: int = 50, max_iterations: int = 100):
        super().__init__()
        self.grid_points = grid_points
        self.max_iterations = max_iterations

    def optimize(
        self,
        snapshots: Dict[str, StrategySnapshot],
        constraints: Optional[PortfolioConstraints] = None,
        old_weights: Optional[Dict[str, float]] = None,
        risk_free_rate: float = 0.0,
    ) -> OptimizationResult:
        """Run Maximum Sharpe optimization."""
        start_time = time.time()
        strategy_ids = list(snapshots.keys())
        n = len(strategy_ids)

        if n == 0:
            return OptimizationResult(
                portfolio_id="",
                method=OptimizationMethod.MAX_SHARPE,
                metrics=OptimizationMetrics(method=OptimizationMethod.MAX_SHARPE),
                status="error",
                message="No strategies provided",
            )

        returns = {sid: snapshots[sid].expected_return for sid in strategy_ids}
        volatilities = {sid: snapshots[sid].expected_volatility for sid in strategy_ids}
        correlations = {}
        for si in strategy_ids:
            correlations[si] = {}
            for sj in strategy_ids:
                if si == sj:
                    correlations[si][sj] = 1.0
                else:
                    correlations[si][sj] = snapshots[si].correlation_to_portfolio

        cov = self._build_covariance_matrix(volatilities, correlations)

        best_weights = None
        best_sharpe = float("-inf")
        iterations = 0

        # Search over risk aversion levels to find max Sharpe
        for lambda_val in [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]:
            iterations += 1
            mv = MeanVarianceOptimizer(risk_aversion=lambda_val)
            result = mv.optimize(snapshots, constraints, old_weights, risk_free_rate)

            sharpe = self._sharpe_ratio(result.weights, returns, cov, risk_free_rate)
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_weights = dict(result.weights)

        if best_weights is None:
            best_weights = {sid: 1.0 / n for sid in strategy_ids}

        elapsed_ms = (time.time() - start_time) * 1000
        metrics = self._build_metrics(
            OptimizationMethod.MAX_SHARPE,
            best_weights,
            returns,
            cov,
            old_weights,
            risk_free_rate,
            iterations,
            True,
            elapsed_ms,
        )

        return OptimizationResult(
            portfolio_id="",
            method=OptimizationMethod.MAX_SHARPE,
            weights=best_weights,
            metrics=metrics,
            iterations=iterations,
        )


class MinVarianceOptimizer(PortfolioOptimizer):
    """Minimum Variance portfolio optimizer."""

    def __init__(self, max_iterations: int = 100):
        super().__init__(risk_aversion=float("inf"))
        self.max_iterations = max_iterations

    def optimize(
        self,
        snapshots: Dict[str, StrategySnapshot],
        constraints: Optional[PortfolioConstraints] = None,
        old_weights: Optional[Dict[str, float]] = None,
        risk_free_rate: float = 0.0,
    ) -> OptimizationResult:
        """Run Minimum Variance optimization."""
        start_time = time.time()
        strategy_ids = list(snapshots.keys())
        n = len(strategy_ids)

        if n == 0:
            return OptimizationResult(
                portfolio_id="",
                method=OptimizationMethod.MIN_VARIANCE,
                metrics=OptimizationMetrics(method=OptimizationMethod.MIN_VARIANCE),
                status="error",
                message="No strategies provided",
            )

        returns = {sid: snapshots[sid].expected_return for sid in strategy_ids}
        volatilities = {sid: snapshots[sid].expected_volatility for sid in strategy_ids}
        correlations = {}
        for si in strategy_ids:
            correlations[si] = {}
            for sj in strategy_ids:
                if si == sj:
                    correlations[si][sj] = 1.0
                else:
                    correlations[si][sj] = snapshots[si].correlation_to_portfolio

        cov = self._build_covariance_matrix(volatilities, correlations)

        # Start from equal weights and minimize variance
        weights = {sid: 1.0 / n for sid in strategy_ids}
        best_weights = dict(weights)
        best_var = float("inf")

        for iteration in range(self.max_iterations):
            weights = self._enforce_weight_constraints(weights, constraints)
            port_var = self._portfolio_variance(weights, cov)

            if port_var < best_var:
                best_var = port_var
                best_weights = dict(weights)

            # Gradient descent on variance
            mrc = self._marginal_risk_contributions(weights, cov)
            grad = {}
            for sid in strategy_ids:
                grad[sid] = -2.0 * mrc[sid]

            step_size = 0.1 / (iteration + 1)
            for sid in strategy_ids:
                weights[sid] += step_size * grad[sid]
                weights[sid] = max(0.0, weights[sid])

            total = sum(weights.values())
            if total > 0:
                weights = {s: w / total for s, w in weights.items()}

        elapsed_ms = (time.time() - start_time) * 1000
        metrics = self._build_metrics(
            OptimizationMethod.MIN_VARIANCE,
            best_weights,
            returns,
            cov,
            old_weights,
            risk_free_rate,
            iterations=self.max_iterations,
            converged=True,
            elapsed_ms=elapsed_ms,
        )

        return OptimizationResult(
            portfolio_id="",
            method=OptimizationMethod.MIN_VARIANCE,
            weights=best_weights,
            metrics=metrics,
            iterations=self.max_iterations,
        )
