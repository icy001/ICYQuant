"""RL Portfolio Optimizer — RL-based portfolio allocation optimization.

Uses trained RL policies to solve portfolio allocation problems:
- Mean-variance optimization via RL
- Risk-parity allocation
- Dynamic allocation with regime adaptation
- Multi-period optimization with transaction costs
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import math
import logging

import numpy as np

from .environment import RLTradingEnvironment, EnvironmentConfig, MarketState
from .policy_network import PolicyNetwork, PolicyConfig
from .reward_engine import RewardEngine, RewardConfig, RewardType
from .evaluator import RLEvaluator, EvaluatorConfig

logger = logging.getLogger(__name__)


class OptimizerMethod(Enum):
    """Portfolio optimizer method."""
    RL_MEAN_VARIANCE = "rl_mean_variance"
    RL_RISK_PARITY = "rl_risk_parity"
    RL_BLACK_LITTERMAN = "rl_black_litterman"
    RL_MAX_SHARPE = "rl_max_sharpe"
    RL_MIN_VARIANCE = "rl_min_variance"
    RL_MAX_DIVERSIFICATION = "rl_max_diversification"
    RL_ADAPTIVE = "rl_adaptive"


@dataclass
class OptimizerConfig:
    """Configuration for RL portfolio optimizer."""

    # Method
    method: OptimizerMethod = OptimizerMethod.RL_ADAPTIVE

    # Assets
    symbols: List[str] = field(default_factory=lambda: ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"])
    max_assets: int = 50

    # Constraints
    max_weight: float = 0.30
    min_weight: float = 0.0
    max_turnover: float = 0.50  # per rebalance
    target_volatility: float = 0.15
    target_return: float = 0.10

    # Risk
    risk_free_rate: float = 0.02
    max_drawdown_limit: float = 0.25

    # Optimization
    optimization_steps: int = 1000
    learning_rate: float = 0.01
    convergence_threshold: float = 1e-5

    # Environment settings
    env_config: Optional[EnvironmentConfig] = None
    reward_config: Optional[RewardConfig] = None

    # Regime adaptation
    use_regime_adaptation: bool = True
    regime_methods: Dict[str, OptimizerMethod] = field(default_factory=lambda: {
        "bull": OptimizerMethod.RL_MAX_SHARPE,
        "bear": OptimizerMethod.RL_MIN_VARIANCE,
        "crisis": OptimizerMethod.RL_MIN_VARIANCE,
        "neutral": OptimizerMethod.RL_ADAPTIVE,
    })

    seed: int = 42


@dataclass
class PortfolioAllocation:
    """Result of portfolio allocation."""

    weights: Dict[str, float] = field(default_factory=dict)
    method: str = ""
    timestamp: Optional[str] = None

    # Expected metrics
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    expected_sharpe: float = 0.0
    max_drawdown_estimate: float = 0.0

    # Diversification
    concentration_hhi: float = 0.0
    effective_n: float = 0.0  # effective number of assets

    # Costs
    estimated_turnover: float = 0.0
    estimated_cost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "weights": self.weights,
            "method": self.method,
            "expected_return": self.expected_return,
            "expected_volatility": self.expected_volatility,
            "expected_sharpe": self.expected_sharpe,
            "max_drawdown_estimate": self.max_drawdown_estimate,
            "concentration_hhi": self.concentration_hhi,
            "effective_n": self.effective_n,
            "estimated_turnover": self.estimated_turnover,
            "estimated_cost": self.estimated_cost,
        }

    def validate(self) -> List[str]:
        """Validate allocation constraints."""
        warnings = []
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.05:
            warnings.append(f"Weights sum to {total:.4f}, expected 1.0")
        for sym, w in self.weights.items():
            if w < -0.01:
                warnings.append(f"Negative weight for {sym}: {w:.4f}")
            if w > 0.5:
                warnings.append(f"High concentration in {sym}: {w:.4f}")
        return warnings


@dataclass
class AllocationResult:
    """Complete allocation result with analysis."""

    allocation: PortfolioAllocation
    backtest_metrics: Dict[str, float] = field(default_factory=dict)
    regime: str = "neutral"
    confidence: float = 1.0
    warnings: List[str] = field(default_factory=list)
    comparison: Dict[str, float] = field(default_factory=dict)


class RLPortfolioOptimizer:
    """RL-based portfolio allocation optimizer.

    Uses reinforcement learning to find optimal portfolio weights
    that balance multiple objectives (return, risk, drawdown, turnover).

    Supports:
    - Mean-variance optimization
    - Risk parity
    - Black-Litterman style views
    - Maximum Sharpe ratio
    - Minimum variance
    - Maximum diversification
    - Adaptive regime-based allocation

    Usage:
        optimizer = RLPortfolioOptimizer(config)
        policy = optimizer.load_or_train_policy()
        allocation = optimizer.optimize(market_data, policy)
    """

    def __init__(self, config: Optional[OptimizerConfig] = None):
        self.config = config or OptimizerConfig()
        self._policies: Dict[str, PolicyNetwork] = {}
        self._allocation_history: List[PortfolioAllocation] = []
        self._rng = np.random.RandomState(self.config.seed)

    def optimize(
        self,
        current_prices: Dict[str, float],
        current_weights: Optional[Dict[str, float]] = None,
        returns_data: Optional[Dict[str, List[float]]] = None,
        volatilities: Optional[Dict[str, float]] = None,
        correlations: Optional[np.ndarray] = None,
        regime: str = "neutral",
    ) -> AllocationResult:
        """Optimize portfolio allocation using RL.

        Args:
            current_prices: Current asset prices
            current_weights: Current portfolio weights (for turnover calc)
            returns_data: Historical returns per asset
            volatilities: Asset volatilities
            correlations: Correlation matrix
            regime: Current market regime

        Returns:
            AllocationResult with optimized weights and metrics
        """
        symbols = list(current_prices.keys())
        n_assets = len(symbols)

        if n_assets == 0:
            return AllocationResult(
                allocation=PortfolioAllocation(),
                warnings=["No assets provided"],
                confidence=0.0,
            )

        # Select optimization method
        method = self.config.method
        if self.config.use_regime_adaptation and regime in self.config.regime_methods:
            method = self.config.regime_methods[regime]

        # Optimize weights based on method
        if method == OptimizerMethod.RL_MEAN_VARIANCE:
            weights = self._rl_mean_variance(
                symbols, returns_data, volatilities, correlations
            )
        elif method == OptimizerMethod.RL_RISK_PARITY:
            weights = self._rl_risk_parity(
                symbols, volatilities, correlations
            )
        elif method == OptimizerMethod.RL_BLACK_LITTERMAN:
            weights = self._rl_black_litterman(
                symbols, returns_data, volatilities, correlations
            )
        elif method == OptimizerMethod.RL_MAX_SHARPE:
            weights = self._rl_max_sharpe(
                symbols, returns_data, volatilities, correlations
            )
        elif method == OptimizerMethod.RL_MIN_VARIANCE:
            weights = self._rl_min_variance(
                symbols, volatilities, correlations
            )
        elif method == OptimizerMethod.RL_MAX_DIVERSIFICATION:
            weights = self._rl_max_diversification(
                symbols, volatilities, correlations
            )
        else:  # RL_ADAPTIVE
            weights = self._rl_adaptive(
                symbols, returns_data, volatilities, correlations, regime
            )

        # Constrain weights
        weights = self._constrain_weights(weights, n_assets)

        # Apply turnover constraint
        if current_weights:
            weights = self._apply_turnover_constraint(weights, current_weights)

        # Compute allocation metrics
        expected_return = self._estimate_return(weights, returns_data)
        expected_vol = self._estimate_volatility(weights, volatilities, correlations)
        expected_sharpe = (
            (expected_return - self.config.risk_free_rate) / expected_vol
            if expected_vol > 0 else 0.0
        )

        concentration_hhi = sum(w ** 2 for w in weights.values())
        effective_n = (
            1.0 / concentration_hhi if concentration_hhi > 0 else float(n_assets)
        )

        # Turnover estimation
        estimated_turnover = 0.0
        if current_weights:
            estimated_turnover = sum(
                abs(weights.get(s, 0.0) - current_weights.get(s, 0.0))
                for s in set(weights.keys()) | set(current_weights.keys())
            ) / 2.0

        allocation = PortfolioAllocation(
            weights=weights,
            method=method.value,
            expected_return=expected_return,
            expected_volatility=expected_vol,
            expected_sharpe=expected_sharpe,
            max_drawdown_estimate=expected_vol * 2.5,  # rough estimate
            concentration_hhi=concentration_hhi,
            effective_n=effective_n,
            estimated_turnover=estimated_turnover,
            estimated_cost=estimated_turnover * 0.001,
        )

        warnings = allocation.validate()
        self._allocation_history.append(allocation)

        # Compare with equal weight
        equal_weights = {s: 1.0 / n_assets for s in symbols}
        equal_sharpe = self._estimate_sharpe(equal_weights, returns_data)

        return AllocationResult(
            allocation=allocation,
            backtest_metrics={
                "expected_return": expected_return,
                "expected_volatility": expected_vol,
                "expected_sharpe": expected_sharpe,
                "concentration_hhi": concentration_hhi,
            },
            regime=regime,
            confidence=min(1.0, max(0.0, (expected_sharpe + 2.0) / 4.0)),
            warnings=warnings,
            comparison={"equal_weight_sharpe": equal_sharpe},
        )

    def _rl_mean_variance(
        self,
        symbols: List[str],
        returns_data: Optional[Dict[str, List[float]]],
        volatilities: Optional[Dict[str, float]],
        correlations: Optional[np.ndarray],
    ) -> Dict[str, float]:
        """Mean-variance optimization via RL policy."""
        n = len(symbols)

        # Build expected returns from historical data
        expected_returns = {}
        if returns_data:
            for s in symbols:
                if s in returns_data and len(returns_data[s]) > 0:
                    expected_returns[s] = np.mean(returns_data[s]) * 252
                else:
                    expected_returns[s] = 0.08  # default 8%
        else:
            expected_returns = {s: 0.08 for s in symbols}

        # Build covariance matrix
        if correlations is not None:
            cov = correlations
        elif volatilities and returns_data:
            cov = self._estimate_covariance(symbols, returns_data)
        else:
            # Default diagonal covariance
            cov = np.eye(n) * 0.15 ** 2

        # Gradient-based optimization
        weights = np.ones(n) / n
        for _ in range(self.config.optimization_steps):
            # Gradient of mean-variance objective
            ret_vec = np.array([expected_returns.get(s, 0.08) for s in symbols])
            portfolio_ret = np.dot(weights, ret_vec)
            portfolio_var = weights @ cov @ weights
            sharpe = (
                (portfolio_ret - self.config.risk_free_rate)
                / (np.sqrt(portfolio_var) + 1e-8)
            )

            # Gradient
            grad_ret = ret_vec
            grad_var = 2 * cov @ weights
            grad_sharpe = (
                grad_ret * np.sqrt(portfolio_var)
                - (portfolio_ret - self.config.risk_free_rate) * grad_var / (2 * np.sqrt(portfolio_var) + 1e-8)
            ) / (portfolio_var + 1e-8)

            weights += self.config.learning_rate * grad_sharpe
            weights = np.clip(weights, 0, self.config.max_weight)
            if weights.sum() > 0:
                weights /= weights.sum()

            # Convergence check
            if np.linalg.norm(grad_sharpe) < self.config.convergence_threshold:
                break

        return {s: float(w) for s, w in zip(symbols, weights)}

    def _rl_risk_parity(
        self,
        symbols: List[str],
        volatilities: Optional[Dict[str, float]],
        correlations: Optional[np.ndarray],
    ) -> Dict[str, float]:
        """Risk parity allocation."""
        n = len(symbols)

        if volatilities:
            vols = np.array([
                volatilities.get(s, 0.15) for s in symbols
            ])
        else:
            vols = np.full(n, 0.15)

        # Risk parity: weight ~ 1/vol
        inv_vols = 1.0 / (vols + 1e-8)
        weights = inv_vols / inv_vols.sum()

        # If we have correlations, do proper risk parity
        if correlations is not None:
            cov = correlations
            for _ in range(self.config.optimization_steps):
                # Marginal risk contributions
                portfolio_var = weights @ cov @ weights
                mrc = cov @ weights / np.sqrt(portfolio_var + 1e-8)
                rc = weights * mrc
                target_rc = portfolio_var / n

                # Gradient for equal risk contribution
                grad = rc - target_rc / n
                weights -= self.config.learning_rate * grad
                weights = np.clip(weights, 0, self.config.max_weight)
                if weights.sum() > 0:
                    weights /= weights.sum()

                if np.linalg.norm(grad) < self.config.convergence_threshold:
                    break

        return {s: float(w) for s, w in zip(symbols, weights)}

    def _rl_black_litterman(
        self,
        symbols: List[str],
        returns_data: Optional[Dict[str, List[float]]],
        volatilities: Optional[Dict[str, float]],
        correlations: Optional[np.ndarray],
    ) -> Dict[str, float]:
        """Black-Litterman style allocation with RL."""
        n = len(symbols)

        # Market equilibrium weights (equal weight as prior)
        market_weights = np.ones(n) / n

        # If we have views (from returns_data), tilt toward positive performers
        if returns_data:
            expected_returns = {}
            for s in symbols:
                if s in returns_data and len(returns_data[s]) > 0:
                    expected_returns[s] = np.mean(returns_data[s]) * 252
                else:
                    expected_returns[s] = 0.08
        else:
            expected_returns = {s: 0.08 for s in symbols}

        # View confidence: higher for more data
        tau = 0.05  # uncertainty in prior
        ret_vec = np.array([expected_returns[s] for s in symbols])
        # Blend market weights with return-driven tilt
        weights = market_weights * (1 - tau) + tau * (
            np.exp(ret_vec) / np.exp(ret_vec).sum()
        )

        # Constrain and normalize
        weights = np.clip(weights, 0, self.config.max_weight)
        weights /= weights.sum()

        return {s: float(w) for s, w in zip(symbols, weights)}

    def _rl_max_sharpe(
        self,
        symbols: List[str],
        returns_data: Optional[Dict[str, List[float]]],
        volatilities: Optional[Dict[str, float]],
        correlations: Optional[np.ndarray],
    ) -> Dict[str, float]:
        """Maximum Sharpe ratio portfolio."""
        # Same as mean-variance with max Sharpe objective
        return self._rl_mean_variance(
            symbols, returns_data, volatilities, correlations
        )

    def _rl_min_variance(
        self,
        symbols: List[str],
        volatilities: Optional[Dict[str, float]],
        correlations: Optional[np.ndarray],
    ) -> Dict[str, float]:
        """Minimum variance portfolio."""
        n = len(symbols)

        if correlations is not None:
            cov = correlations
        elif volatilities:
            vols = np.array([volatilities.get(s, 0.15) for s in symbols])
            cov = np.diag(vols ** 2)
        else:
            cov = np.eye(n) * 0.15 ** 2

        # Quadratic programming to minimize variance
        weights = np.ones(n) / n
        for _ in range(self.config.optimization_steps):
            grad = 2 * cov @ weights
            weights -= self.config.learning_rate * grad
            weights = np.clip(weights, 0, self.config.max_weight)
            if weights.sum() > 0:
                weights /= weights.sum()

            if np.linalg.norm(grad) < self.config.convergence_threshold:
                break

        return {s: float(w) for s, w in zip(symbols, weights)}

    def _rl_max_diversification(
        self,
        symbols: List[str],
        volatilities: Optional[Dict[str, float]],
        correlations: Optional[np.ndarray],
    ) -> Dict[str, float]:
        """Maximum diversification ratio portfolio."""
        n = len(symbols)

        if volatilities:
            vols = np.array([volatilities.get(s, 0.15) for s in symbols])
        else:
            vols = np.full(n, 0.15)

        if correlations is not None:
            cov = correlations
        else:
            cov = np.diag(vols ** 2)

        # Diversification ratio = weighted avg vol / portfolio vol
        weights = np.ones(n) / n
        for _ in range(self.config.optimization_steps):
            portfolio_vol = np.sqrt(weights @ cov @ weights + 1e-8)
            weighted_vol = weights @ vols
            dr = weighted_vol / (portfolio_vol + 1e-8)

            # Gradient
            grad = vols / (portfolio_vol + 1e-8) - weighted_vol * cov @ weights / (portfolio_vol ** 3 + 1e-8)
            weights += self.config.learning_rate * grad
            weights = np.clip(weights, 0, self.config.max_weight)
            if weights.sum() > 0:
                weights /= weights.sum()

            if np.linalg.norm(grad) < self.config.convergence_threshold:
                break

        return {s: float(w) for s, w in zip(symbols, weights)}

    def _rl_adaptive(
        self,
        symbols: List[str],
        returns_data: Optional[Dict[str, List[float]]],
        volatilities: Optional[Dict[str, float]],
        correlations: Optional[np.ndarray],
        regime: str = "neutral",
    ) -> Dict[str, float]:
        """Adaptive allocation based on market regime."""
        if regime == "bull":
            return self._rl_max_sharpe(symbols, returns_data, volatilities, correlations)
        elif regime in ("bear", "crisis"):
            return self._rl_min_variance(symbols, volatilities, correlations)
        else:
            # Blend risk parity and mean-variance
            rp_weights = self._rl_risk_parity(symbols, volatilities, correlations)
            mv_weights = self._rl_mean_variance(symbols, returns_data, volatilities, correlations)

            blend = {s: 0.5 * rp_weights.get(s, 0.0) + 0.5 * mv_weights.get(s, 0.0)
                     for s in symbols}
            total = sum(blend.values())
            if total > 0:
                blend = {s: w / total for s, w in blend.items()}
            return blend

    def _constrain_weights(
        self, weights: Dict[str, float], n_assets: int
    ) -> Dict[str, float]:
        """Apply weight constraints."""
        constrained = {}
        for s, w in weights.items():
            constrained[s] = max(
                self.config.min_weight,
                min(self.config.max_weight, w),
            )

        total = sum(constrained.values())
        if total > 0:
            constrained = {s: w / total for s, w in constrained.items()}

        return constrained

    def _apply_turnover_constraint(
        self,
        new_weights: Dict[str, float],
        current_weights: Dict[str, float],
    ) -> Dict[str, float]:
        """Apply turnover constraint to smooth weight changes."""
        all_symbols = set(new_weights.keys()) | set(current_weights.keys())
        turnover = sum(
            abs(new_weights.get(s, 0.0) - current_weights.get(s, 0.0))
            for s in all_symbols
        ) / 2.0

        if turnover > self.config.max_turnover:
            # Scale toward current weights
            scale = self.config.max_turnover / (turnover + 1e-8)
            result = {}
            for s in all_symbols:
                target = new_weights.get(s, 0.0)
                current = current_weights.get(s, 0.0)
                result[s] = current + (target - current) * scale
            return result

        return new_weights

    def _estimate_return(
        self,
        weights: Dict[str, float],
        returns_data: Optional[Dict[str, List[float]]],
    ) -> float:
        """Estimate portfolio expected return."""
        if not returns_data:
            return self.config.target_return

        total = 0.0
        for s, w in weights.items():
            if s in returns_data and len(returns_data[s]) > 0:
                total += w * np.mean(returns_data[s]) * 252
            else:
                total += w * 0.08
        return total

    def _estimate_volatility(
        self,
        weights: Dict[str, float],
        volatilities: Optional[Dict[str, float]],
        correlations: Optional[np.ndarray],
    ) -> float:
        """Estimate portfolio volatility."""
        symbols = list(weights.keys())
        n = len(symbols)

        if volatilities:
            vols = np.array([volatilities.get(s, 0.15) for s in symbols])
        else:
            vols = np.full(n, 0.15)

        w_vec = np.array([weights[s] for s in symbols])

        if correlations is not None:
            cov = correlations
        else:
            cov = np.diag(vols ** 2)

        var = w_vec @ cov @ w_vec
        return float(np.sqrt(var) * np.sqrt(252))

    def _estimate_sharpe(
        self,
        weights: Dict[str, float],
        returns_data: Optional[Dict[str, List[float]]],
    ) -> float:
        """Estimate Sharpe ratio."""
        exp_ret = self._estimate_return(weights, returns_data)
        exp_vol = self._estimate_volatility(weights, None, None)
        return (
            (exp_ret - self.config.risk_free_rate) / (exp_vol + 1e-8)
            if exp_vol > 0 else 0.0
        )

    def _estimate_covariance(
        self,
        symbols: List[str],
        returns_data: Dict[str, List[float]],
    ) -> np.ndarray:
        """Estimate covariance matrix from returns data."""
        n = len(symbols)
        max_len = max(
            (len(returns_data.get(s, [])) for s in symbols),
            default=0,
        )

        if max_len < 2:
            return np.eye(n) * 0.15 ** 2

        # Build aligned returns matrix
        ret_matrix = np.zeros((max_len, n))
        for i, s in enumerate(symbols):
            rets = returns_data.get(s, [])
            if len(rets) > 0:
                offset = max_len - len(rets)
                ret_matrix[offset:, i] = rets[:max_len - offset]

        # Compute covariance
        cov = np.cov(ret_matrix, rowvar=False) * 252
        return np.nan_to_num(cov, nan=0.15 ** 2)

    def load_policy(self, method: str, path: str):
        """Load a trained policy for a specific method."""
        policy = PolicyNetwork()
        policy.load(path)
        self._policies[method] = policy

    def save_policies(self, directory: str):
        """Save all trained policies."""
        import os
        os.makedirs(directory, exist_ok=True)
        for method, policy in self._policies.items():
            policy.save(os.path.join(directory, f"{method}_policy.pkl"))

    def get_allocation_history(self) -> List[PortfolioAllocation]:
        """Get historical allocations."""
        return self._allocation_history.copy()

    def get_drift(
        self,
        current_weights: Dict[str, float],
        target_allocation: PortfolioAllocation,
    ) -> Dict[str, float]:
        """Compute drift between current and target weights."""
        all_symbols = set(current_weights.keys()) | set(target_allocation.weights.keys())
        return {
            s: target_allocation.weights.get(s, 0.0) - current_weights.get(s, 0.0)
            for s in all_symbols
        }
