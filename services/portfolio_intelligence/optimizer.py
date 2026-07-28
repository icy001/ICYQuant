"""AI Portfolio Optimizer — multi-objective portfolio optimization engine.

Supports mean-variance, risk parity, minimum variance, maximum Sharpe,
and Black-Litterman optimization with constraints. Includes efficient
frontier computation and sensitivity analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Objective(str, Enum):
    """Optimization objectives."""

    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance"
    MAX_RETURN = "max_return"
    RISK_PARITY = "risk_parity"
    TARGET_RISK = "target_risk"
    TARGET_RETURN = "target_return"
    BLACK_LITTERMAN = "black_litterman"


class ConstraintType(str, Enum):
    """Constraint types for optimization."""

    WEIGHT_SUM = "weight_sum"  # weights must sum to 1
    LONG_ONLY = "long_only"  # no short positions
    BOUNDS = "bounds"  # min/max per asset
    SECTOR = "sector"  # max sector exposure
    TURNOVER = "turnover"  # max turnover limit
    CARDINALITY = "cardinality"  # max number of positions
    LEVERAGE = "leverage"  # max gross exposure


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class OptimizationConstraint:
    """Single optimization constraint.

    Attributes:
        constraint_type: Type of constraint.
        value: Constraint value (bound, limit, target).
        params: Additional constraint parameters.
    """

    constraint_type: ConstraintType
    value: float = 0.0
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class EfficientFrontierPoint:
    """Single point on the efficient frontier.

    Attributes:
        expected_return: Portfolio expected return.
        expected_volatility: Portfolio expected volatility.
        sharpe_ratio: Sharpe ratio at this point.
        weights: Portfolio weights for this point.
        is_tangency: Whether this is the tangency (max Sharpe) portfolio.
    """

    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    weights: dict[str, float]
    is_tangency: bool = False


@dataclass
class OptimizationResult:
    """Portfolio optimization result.

    Attributes:
        objective: The optimization objective used.
        weights: Optimal portfolio weights.
        expected_return: Expected annual return.
        expected_volatility: Expected annual volatility.
        sharpe_ratio: Expected Sharpe ratio.
        diversification_ratio: Diversification metric.
        constraints_applied: List of active constraints.
        efficient_frontier: Points on the efficient frontier.
        sensitivity: Sensitivity analysis results.
        timestamp: Optimization time.
        metadata: Additional optimization context.
    """

    objective: Objective
    weights: dict[str, float]
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    diversification_ratio: float = 0.0
    constraints_applied: list[ConstraintType] = field(default_factory=list)
    efficient_frontier: list[EfficientFrontierPoint] = field(default_factory=list)
    sensitivity: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_weight(self) -> float:
        """Sum of optimal weights."""
        return sum(self.weights.values())

    @property
    def long_only(self) -> bool:
        """Whether all positions are long."""
        return all(w >= 0 for w in self.weights.values())

    @property
    def active_positions(self) -> int:
        """Number of positions with non-zero weight."""
        return sum(1 for w in self.weights.values() if abs(w) > 0.001)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "objective": self.objective.value,
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "expected_return": round(self.expected_return, 4),
            "expected_volatility": round(self.expected_volatility, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "active_positions": self.active_positions,
        }


# ---------------------------------------------------------------------------
# PortfolioOptimizer
# ---------------------------------------------------------------------------


class PortfolioOptimizer:
    """AI portfolio optimization engine.

    Uses analytic approximations for portfolio optimization without
    requiring external QP solvers. Supports multi-objective optimization,
    constraints, efficient frontier computation, and sensitivity analysis.

    Attributes:
        objective: Default optimization objective.
        risk_free_rate: Risk-free rate for Sharpe ratio computation.
        max_frontier_points: Number of points on efficient frontier.
        history: Past optimization results.
    """

    DEFAULT_RETURNS: dict[str, float] = {
        "EQUITY": 0.08,
        "FIXED_INCOME": 0.04,
        "COMMODITY": 0.06,
        "CASH": 0.03,
        "CRYPTO": 0.20,
        "REAL_ESTATE": 0.07,
    }

    DEFAULT_VOLATILITIES: dict[str, float] = {
        "EQUITY": 0.18,
        "FIXED_INCOME": 0.05,
        "COMMODITY": 0.20,
        "CASH": 0.005,
        "CRYPTO": 0.60,
        "REAL_ESTATE": 0.12,
    }

    def __init__(
        self,
        objective: Objective = Objective.MAX_SHARPE,
        risk_free_rate: float = 0.03,
        max_frontier_points: int = 20,
    ) -> None:
        """Initialize the portfolio optimizer.

        Args:
            objective: Default optimization objective.
            risk_free_rate: Risk-free rate for Sharpe/Sortino.
            max_frontier_points: Points to compute on efficient frontier.
        """
        self.objective = objective
        self.risk_free_rate = risk_free_rate
        self.max_frontier_points = max_frontier_points
        self.history: list[OptimizationResult] = []

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------

    def optimize(
        self,
        assets: list[dict[str, Any]],
        objective: Optional[Objective] = None,
        constraints: Optional[dict[str, Any]] = None,
    ) -> OptimizationResult:
        """Compute optimal portfolio weights.

        Args:
            assets: Asset dicts with keys: symbol, expected_return,
                    volatility, correlation (optional: views).
            objective: Override default optimization objective.
            constraints: Constraint settings (bounds, turnover, etc.).

        Returns:
            OptimizationResult with optimal weights and metrics.
        """
        objective = objective or self.objective
        constraints = constraints or {}

        symbols = [a["symbol"] for a in assets]
        returns = {}
        vols = {}
        for a in assets:
            s = a["symbol"]
            returns[s] = a.get("expected_return", self.DEFAULT_RETURNS.get(s, 0.06))
            vols[s] = max(a.get("volatility", self.DEFAULT_VOLATILITIES.get(s, 0.15)), 0.001)

        n = len(symbols)

        # Apply objective-based base weights
        if objective == Objective.MAX_SHARPE:
            base_weights = self._solve_max_sharpe(symbols, returns, vols, constraints)
        elif objective == Objective.MIN_VARIANCE:
            base_weights = self._solve_min_variance(symbols, vols, constraints)
        elif objective == Objective.MAX_RETURN:
            base_weights = self._solve_max_return(symbols, returns, constraints)
        elif objective == Objective.RISK_PARITY:
            base_weights = self._solve_risk_parity(symbols, vols, constraints)
        elif objective == Objective.TARGET_RISK:
            target_vol = constraints.get("target_volatility", 0.15)
            base_weights = self._solve_target_risk(symbols, returns, vols, target_vol, constraints)
        elif objective == Objective.TARGET_RETURN:
            target_ret = constraints.get("target_return", 0.08)
            base_weights = self._solve_target_return(symbols, returns, vols, target_ret, constraints)
        elif objective == Objective.BLACK_LITTERMAN:
            views = constraints.get("views", {})
            base_weights = self._solve_black_litterman(symbols, returns, vols, views, constraints)
        else:
            base_weights = self._solve_risk_parity(symbols, vols, constraints)

        # Apply bounds
        bounds = constraints.get("bounds", {})
        for s in symbols:
            lo = bounds.get(s, {}).get("min", 0.0)
            hi = bounds.get(s, {}).get("max", 1.0)
            w = base_weights.get(s, 0.0)
            base_weights[s] = max(lo, min(hi, w))

        # Normalize to 1.0
        total = sum(base_weights.values())
        if total > 0:
            base_weights = {k: v / total for k, v in base_weights.items()}

        # Portfolio metrics
        exp_ret = sum(
            base_weights.get(s, 0.0) * returns.get(s, 0.06) for s in symbols
        )
        exp_vol = (
            sum(base_weights.get(s, 0.0) ** 2 * vols.get(s, 0.15) ** 2 for s in symbols)
        ) ** 0.5
        sharpe = (exp_ret - self.risk_free_rate) / max(exp_vol, 0.0001)

        # Diversification ratio
        avg_vol = sum(base_weights.get(s, 0.0) * vols.get(s, 0.15) for s in symbols)
        div_ratio = avg_vol / max(exp_vol, 0.0001) if exp_vol > 0 else 1.0
        div_norm = max(0.0, min(1.0, (div_ratio - 1.0) / 2.0))

        # Efficient frontier
        frontier = self._compute_frontier(symbols, returns, vols, constraints)

        # Sensitivity analysis
        sensitivity = self._sensitivity_analysis(symbols, base_weights, returns, vols)

        active_constraints = []
        if bounds:
            active_constraints.append(ConstraintType.BOUNDS)
        active_constraints.append(ConstraintType.WEIGHT_SUM)
        active_constraints.append(ConstraintType.LONG_ONLY)

        result = OptimizationResult(
            objective=objective,
            weights=base_weights,
            expected_return=exp_ret,
            expected_volatility=exp_vol,
            sharpe_ratio=sharpe,
            diversification_ratio=div_norm,
            constraints_applied=active_constraints,
            efficient_frontier=frontier,
            sensitivity=sensitivity,
        )

        self.history.append(result)
        return result

    # ------------------------------------------------------------------
    # Optimization Solvers (Analytic Approximations)
    # ------------------------------------------------------------------

    def _solve_max_sharpe(
        self,
        symbols: list[str],
        returns: dict[str, float],
        vols: dict[str, float],
        constraints: dict[str, Any],
    ) -> dict[str, float]:
        """Max Sharpe: weight ∝ excess_return / variance."""
        excess = {}
        for s in symbols:
            excess[s] = max(returns.get(s, 0.06) - self.risk_free_rate, 0.0)

        raw = {}
        for s in symbols:
            v = vols.get(s, 0.15)
            raw[s] = excess[s] / max(v**2, 0.0001)

        total = sum(raw.values())
        if total == 0:
            return self._equal_weight(symbols)

        return {s: raw[s] / total for s in symbols}

    def _solve_min_variance(
        self,
        symbols: list[str],
        vols: dict[str, float],
        constraints: dict[str, Any],
    ) -> dict[str, float]:
        """Min variance: weight ∝ 1/variance."""
        raw = {}
        for s in symbols:
            v = vols.get(s, 0.15)
            raw[s] = 1.0 / max(v**2, 0.0001)

        total = sum(raw.values())
        if total == 0:
            return self._equal_weight(symbols)

        return {s: raw[s] / total for s in symbols}

    def _solve_max_return(
        self,
        symbols: list[str],
        returns: dict[str, float],
        constraints: dict[str, Any],
    ) -> dict[str, float]:
        """Max return: all in on the highest expected return asset."""
        best = max(symbols, key=lambda s: returns.get(s, 0.0))
        weights = {s: 0.0 for s in symbols}
        weights[best] = 1.0
        return weights

    def _solve_risk_parity(
        self,
        symbols: list[str],
        vols: dict[str, float],
        constraints: dict[str, Any],
    ) -> dict[str, float]:
        """Risk parity: weight ∝ 1/vol."""
        raw = {}
        for s in symbols:
            raw[s] = 1.0 / max(vols.get(s, 0.15), 0.001)

        total = sum(raw.values())
        if total == 0:
            return self._equal_weight(symbols)

        return {s: raw[s] / total for s in symbols}

    def _solve_target_risk(
        self,
        symbols: list[str],
        returns: dict[str, float],
        vols: dict[str, float],
        target_vol: float,
        constraints: dict[str, Any],
    ) -> dict[str, float]:
        """Target risk: start with max Sharpe, scale to target vol."""
        base = self._solve_max_sharpe(symbols, returns, vols, constraints)
        base_vol = (
            sum(base.get(s, 0) ** 2 * vols.get(s, 0.15) ** 2 for s in symbols)
        ) ** 0.5
        if base_vol == 0:
            return base

        scale = target_vol / base_vol
        return {s: min(1.0, base.get(s, 0) * scale) for s in symbols}

    def _solve_target_return(
        self,
        symbols: list[str],
        returns: dict[str, float],
        vols: dict[str, float],
        target_ret: float,
        constraints: dict[str, Any],
    ) -> dict[str, float]:
        """Target return: blend max-return with min-variance to hit target."""
        max_ret = self._solve_max_return(symbols, returns, constraints)
        min_var = self._solve_min_variance(symbols, vols, constraints)

        max_ret_exp = sum(max_ret.get(s, 0) * returns.get(s, 0.06) for s in symbols)
        min_var_exp = sum(min_var.get(s, 0) * returns.get(s, 0.06) for s in symbols)

        if abs(max_ret_exp - min_var_exp) < 0.0001:
            return max_ret

        # Linear blend to hit target return
        alpha = (target_ret - min_var_exp) / (max_ret_exp - min_var_exp)
        alpha = max(0.0, min(1.0, alpha))

        return {
            s: (1 - alpha) * min_var.get(s, 0) + alpha * max_ret.get(s, 0)
            for s in symbols
        }

    def _solve_black_litterman(
        self,
        symbols: list[str],
        returns: dict[str, float],
        vols: dict[str, float],
        views: dict[str, float],
        constraints: dict[str, Any],
    ) -> dict[str, float]:
        """Black-Litterman: equilibrium (risk parity) + investor views."""
        eq_weights = self._solve_risk_parity(symbols, vols, constraints)
        tau = 0.025

        adjusted = {}
        for s in symbols:
            eq_w = eq_weights.get(s, 0.0)
            view = views.get(s, 0.0)
            tilt = 0.3 * view * tau
            adjusted[s] = max(0.0, eq_w * (1.0 + tilt))

        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted

    # ------------------------------------------------------------------
    # Efficient Frontier
    # ------------------------------------------------------------------

    def _compute_frontier(
        self,
        symbols: list[str],
        returns: dict[str, float],
        vols: dict[str, float],
        constraints: dict[str, Any],
    ) -> list[EfficientFrontierPoint]:
        """Compute approximate efficient frontier."""
        frontier: list[EfficientFrontierPoint] = []
        n = len(symbols)

        # Compute min-var and max-Sharpe portfolios as anchor points
        min_var_weights = self._solve_min_variance(symbols, vols, constraints)
        max_sr_weights = self._solve_max_sharpe(symbols, returns, vols, constraints)

        # Blend between min-var and max-Sharpe
        best_sharpe = -float("inf")
        tangency_idx = -1

        for i in range(self.max_frontier_points):
            alpha = i / max(self.max_frontier_points - 1, 1)
            weights = {}
            for s in symbols:
                weights[s] = (1 - alpha) * min_var_weights.get(s, 0) + alpha * max_sr_weights.get(s, 0)

            total = sum(weights.values())
            if total > 0:
                weights = {k: v / total for k, v in weights.items()}

            exp_ret = sum(weights.get(s, 0) * returns.get(s, 0.06) for s in symbols)
            exp_vol = (
                sum(weights.get(s, 0) ** 2 * vols.get(s, 0.15) ** 2 for s in symbols)
            ) ** 0.5
            sharpe = (exp_ret - self.risk_free_rate) / max(exp_vol, 0.0001)

            if sharpe > best_sharpe:
                best_sharpe = sharpe
                tangency_idx = i

            frontier.append(
                EfficientFrontierPoint(
                    expected_return=exp_ret,
                    expected_volatility=exp_vol,
                    sharpe_ratio=sharpe,
                    weights=weights,
                    is_tangency=False,
                )
            )

        # Mark tangency portfolio
        if 0 <= tangency_idx < len(frontier):
            frontier[tangency_idx].is_tangency = True

        return frontier

    # ------------------------------------------------------------------
    # Sensitivity Analysis
    # ------------------------------------------------------------------

    def _sensitivity_analysis(
        self,
        symbols: list[str],
        weights: dict[str, float],
        returns: dict[str, float],
        vols: dict[str, float],
    ) -> dict[str, Any]:
        """Compute sensitivity of portfolio metrics to parameter changes."""
        # Marginal contribution to risk (MCTR)
        port_vol = (
            sum(weights.get(s, 0) ** 2 * vols.get(s, 0.15) ** 2 for s in symbols)
        ) ** 0.5

        mctr = {}
        for s in symbols:
            if port_vol > 0:
                mctr[s] = weights.get(s, 0) * vols.get(s, 0.15) ** 2 / port_vol
            else:
                mctr[s] = 0.0

        # Marginal contribution to return
        mctr_return = {s: returns.get(s, 0.06) for s in symbols}

        # Key sensitivities
        worst_contributor = max(mctr, key=mctr.get) if mctr else ""
        best_contributor = max(mctr_return, key=mctr_return.get) if mctr_return else ""

        return {
            "portfolio_volatility": round(port_vol, 4),
            "marginal_risk_contribution": {s: round(v, 6) for s, v in mctr.items()},
            "worst_risk_contributor": worst_contributor,
            "best_return_contributor": best_contributor,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _equal_weight(self, symbols: list[str]) -> dict[str, float]:
        """Equal weight helper."""
        n = max(len(symbols), 1)
        return {s: 1.0 / n for s in symbols}

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_optimize(
        self,
        symbols: list[str],
        objective: Optional[Objective] = None,
    ) -> dict[str, Any]:
        """Quick optimization with default parameters.

        Args:
            symbols: List of asset symbols.
            objective: Override default objective.

        Returns:
            Dict with optimal weights and portfolio metrics.
        """
        assets = [
            {
                "symbol": s,
                "expected_return": self.DEFAULT_RETURNS.get(s, 0.06),
                "volatility": self.DEFAULT_VOLATILITIES.get(s, 0.15),
            }
            for s in symbols
        ]
        result = self.optimize(assets, objective=objective)
        return {
            "objective": result.objective.value,
            "weights": {k: round(v, 4) for k, v in result.weights.items()},
            "expected_return": round(result.expected_return, 4),
            "expected_volatility": round(result.expected_volatility, 4),
            "sharpe_ratio": round(result.sharpe_ratio, 4),
            "active_positions": result.active_positions,
        }

    def last_result(self) -> Optional[OptimizationResult]:
        """Return the most recent optimization result."""
        return self.history[-1] if self.history else None

    def clear(self) -> None:
        """Reset optimization history."""
        self.history.clear()
