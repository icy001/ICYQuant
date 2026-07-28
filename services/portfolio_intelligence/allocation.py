"""AI Asset Allocation Engine — strategic & tactical portfolio allocation.

Supports multiple allocation strategies including risk parity, minimum variance,
Black-Litterman, momentum-based, and adaptive allocation across asset classes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AssetClass(str, Enum):
    """Major asset classes for allocation."""

    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    COMMODITY = "commodity"
    CASH = "cash"
    ALTERNATIVE = "alternative"
    CRYPTO = "crypto"
    REAL_ESTATE = "real_estate"
    PRIVATE_EQUITY = "private_equity"


class AllocationStrategy(str, Enum):
    """Allocation strategy types."""

    EQUAL_WEIGHT = "equal_weight"
    MARKET_CAP = "market_cap"
    RISK_PARITY = "risk_parity"
    MIN_VARIANCE = "min_variance"
    MOMENTUM_BASED = "momentum_based"
    BLACK_LITTERMAN = "black_litterman"
    ADAPTIVE = "adaptive"


class Horizon(str, Enum):
    """Investment horizon for allocation decisions."""

    SHORT_TERM = "short_term"  # < 3 months
    MEDIUM_TERM = "medium_term"  # 3-12 months
    LONG_TERM = "long_term"  # > 12 months


class RiskTolerance(str, Enum):
    """Risk tolerance profile."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class AssetAllocation:
    """Single asset allocation entry.

    Attributes:
        asset_class: The asset class being allocated.
        target_weight: The target weight (0.0–1.0) for this asset class.
        current_weight: The current portfolio weight (0.0–1.0).
        drift: Allocation drift = current_weight - target_weight.
        constraints: Per-asset constraints (min/max weight, lock status).
    """

    asset_class: AssetClass
    target_weight: float
    current_weight: float = 0.0
    constraints: dict[str, Any] = field(default_factory=dict)

    @property
    def drift(self) -> float:
        """Drift from target: positive = overweight, negative = underweight."""
        return self.current_weight - self.target_weight

    @property
    def is_overweight(self) -> bool:
        """Whether the position is overweight beyond threshold."""
        threshold = self.constraints.get("drift_threshold", 0.05)
        return self.drift > threshold

    @property
    def is_underweight(self) -> bool:
        """Whether the position is underweight beyond threshold."""
        threshold = self.constraints.get("drift_threshold", 0.05)
        return self.drift < -threshold


@dataclass
class AllocationResult:
    """Full allocation result from the engine.

    Attributes:
        allocations: List of per-asset allocations.
        strategy: The strategy used.
        horizon: The investment horizon applied.
        risk_tolerance: Risk tolerance profile.
        expected_return: Portfolio expected annual return.
        expected_volatility: Portfolio expected annual volatility.
        sharpe_ratio: Expected Sharpe ratio.
        diversification_ratio: Diversification score (0–1).
        timestamp: When the allocation was computed.
        metadata: Additional strategy-specific data.
    """

    allocations: list[AssetAllocation]
    strategy: AllocationStrategy
    horizon: Horizon
    risk_tolerance: RiskTolerance = RiskTolerance.MODERATE
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    diversification_ratio: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_weight(self) -> float:
        """Sum of all target weights (should be ~1.0)."""
        return sum(a.target_weight for a in self.allocations)

    @property
    def is_valid(self) -> bool:
        """Check if allocation weights sum to approximately 1.0."""
        return abs(self.total_weight - 1.0) < 0.01

    def to_dict(self) -> dict[str, float]:
        """Return allocations as {asset_class: weight} dict."""
        return {a.asset_class.value: a.target_weight for a in self.allocations}


# ---------------------------------------------------------------------------
# AssetAllocationEngine
# ---------------------------------------------------------------------------


class AssetAllocationEngine:
    """AI-driven asset allocation engine.

    Combines strategic (long-term) and tactical (short-term) allocation
    signals to produce optimal portfolio weights across asset classes.

    Attributes:
        strategy: The primary allocation strategy to apply.
        history: Past allocation results for trend analysis.
        DEFAULT_WEIGHTS: Conservative baseline allocation weights.
        RISK_PROFILES: Weight adjustments per risk tolerance.
    """

    DEFAULT_WEIGHTS: dict[AssetClass, float] = {
        AssetClass.EQUITY: 0.40,
        AssetClass.FIXED_INCOME: 0.25,
        AssetClass.COMMODITY: 0.10,
        AssetClass.CASH: 0.10,
        AssetClass.ALTERNATIVE: 0.05,
        AssetClass.CRYPTO: 0.03,
        AssetClass.REAL_ESTATE: 0.05,
        AssetClass.PRIVATE_EQUITY: 0.02,
    }

    RISK_PROFILES: dict[RiskTolerance, dict[str, float]] = {
        RiskTolerance.CONSERVATIVE: {
            "equity_multiplier": 0.6,
            "fixed_income_multiplier": 1.5,
            "cash_minimum": 0.15,
        },
        RiskTolerance.MODERATE: {
            "equity_multiplier": 1.0,
            "fixed_income_multiplier": 1.0,
            "cash_minimum": 0.05,
        },
        RiskTolerance.AGGRESSIVE: {
            "equity_multiplier": 1.4,
            "fixed_income_multiplier": 0.5,
            "cash_minimum": 0.02,
        },
    }

    STRATEGY_SELECTION: dict[AllocationStrategy, list[str]] = {
        AllocationStrategy.EQUAL_WEIGHT: ["equal_weight"],
        AllocationStrategy.MARKET_CAP: ["market_cap", "capitalization"],
        AllocationStrategy.RISK_PARITY: ["risk_parity", "equal_risk_contribution"],
        AllocationStrategy.MIN_VARIANCE: ["minimum_variance", "min_vol"],
        AllocationStrategy.MOMENTUM_BASED: ["momentum", "trend_following"],
        AllocationStrategy.BLACK_LITTERMAN: ["black_litterman", "bayesian"],
        AllocationStrategy.ADAPTIVE: ["adaptive", "multi_factor"],
    }

    def __init__(
        self,
        strategy: AllocationStrategy = AllocationStrategy.RISK_PARITY,
        horizon: Horizon = Horizon.MEDIUM_TERM,
        risk_tolerance: RiskTolerance = RiskTolerance.MODERATE,
    ) -> None:
        """Initialize the allocation engine.

        Args:
            strategy: Primary allocation strategy to use.
            horizon: Investment horizon for allocation decisions.
            risk_tolerance: Risk tolerance profile.
        """
        self.strategy = strategy
        self.horizon = horizon
        self.risk_tolerance = risk_tolerance
        self.history: list[AllocationResult] = []

    # ------------------------------------------------------------------
    # Allocation Methods
    # ------------------------------------------------------------------

    def allocate(
        self,
        asset_data: Optional[dict[AssetClass, dict[str, Any]]] = None,
        strategy: Optional[AllocationStrategy] = None,
        constraints: Optional[dict[AssetClass, dict[str, Any]]] = None,
        views: Optional[dict[AssetClass, float]] = None,
    ) -> AllocationResult:
        """Compute optimal allocation weights.

        Args:
            asset_data: Per-asset statistics (vol, return, corr, market_cap).
            strategy: Override the default strategy.
            constraints: Per-asset constraints (min_weight, max_weight, locked).
            views: Investor views for Black-Litterman (expected excess returns).

        Returns:
            AllocationResult with computed target weights.
        """
        strategy = strategy or self.strategy
        constraints = constraints or {}
        asset_data = asset_data or {}

        profile = self.RISK_PROFILES[self.risk_tolerance]
        asset_classes = list(AssetClass)
        base_weights = self.DEFAULT_WEIGHTS.copy()

        # Apply risk tolerance adjustments
        for ac, weight in base_weights.items():
            if ac == AssetClass.EQUITY:
                base_weights[ac] = weight * profile["equity_multiplier"]
            elif ac == AssetClass.FIXED_INCOME:
                base_weights[ac] = weight * profile["fixed_income_multiplier"]

        # Enforce cash minimum
        if base_weights.get(AssetClass.CASH, 0) < profile["cash_minimum"]:
            base_weights[AssetClass.CASH] = profile["cash_minimum"]

        # Normalize to 1.0
        total = sum(base_weights.values())
        base_weights = {k: v / total for k, v in base_weights.items()}

        # Apply strategy-specific logic
        if strategy == AllocationStrategy.EQUAL_WEIGHT:
            weights = self._allocate_equal_weight(asset_classes, constraints)
        elif strategy == AllocationStrategy.MARKET_CAP:
            weights = self._allocate_market_cap(asset_classes, asset_data, constraints)
        elif strategy == AllocationStrategy.RISK_PARITY:
            weights = self._allocate_risk_parity(asset_classes, asset_data, constraints)
        elif strategy == AllocationStrategy.MIN_VARIANCE:
            weights = self._allocate_min_variance(asset_classes, asset_data, constraints)
        elif strategy == AllocationStrategy.MOMENTUM_BASED:
            weights = self._allocate_momentum(asset_classes, asset_data, constraints)
        elif strategy == AllocationStrategy.BLACK_LITTERMAN:
            weights = self._allocate_black_litterman(asset_classes, asset_data, views, constraints)
        elif strategy == AllocationStrategy.ADAPTIVE:
            weights = self._allocate_adaptive(asset_classes, asset_data, constraints)
        else:
            weights = base_weights

        # Build allocation list
        allocations = []
        for ac in asset_classes:
            target = weights.get(ac, base_weights.get(ac, 0.0))
            cons = constraints.get(ac, {})
            allocations.append(
                AssetAllocation(
                    asset_class=ac,
                    target_weight=target,
                    current_weight=cons.get("current_weight", 0.0),
                    constraints=cons,
                )
            )

        # Compute portfolio metrics
        exp_ret, exp_vol = self._estimate_portfolio_metrics(allocations, asset_data)
        sharpe = exp_ret / exp_vol if exp_vol > 0 else 0.0
        div_ratio = self._compute_diversification_ratio(allocations)

        result = AllocationResult(
            allocations=allocations,
            strategy=strategy,
            horizon=self.horizon,
            risk_tolerance=self.risk_tolerance,
            expected_return=exp_ret,
            expected_volatility=exp_vol,
            sharpe_ratio=sharpe,
            diversification_ratio=div_ratio,
        )

        self.history.append(result)
        return result

    # ------------------------------------------------------------------
    # Strategy Implementations
    # ------------------------------------------------------------------

    def _allocate_equal_weight(
        self,
        asset_classes: list[AssetClass],
        constraints: dict[AssetClass, dict[str, Any]],
    ) -> dict[AssetClass, float]:
        """Equal-weight allocation across all active asset classes."""
        active = [
            ac
            for ac in asset_classes
            if not constraints.get(ac, {}).get("excluded", False)
        ]
        n = max(len(active), 1)
        weight = 1.0 / n
        return {ac: weight for ac in asset_classes if ac in active}

    def _allocate_market_cap(
        self,
        asset_classes: list[AssetClass],
        asset_data: dict[AssetClass, dict[str, Any]],
        constraints: dict[AssetClass, dict[str, Any]],
    ) -> dict[AssetClass, float]:
        """Market-cap weighted allocation."""
        caps = {}
        for ac in asset_classes:
            if constraints.get(ac, {}).get("excluded", False):
                caps[ac] = 0.0
            else:
                caps[ac] = asset_data.get(ac, {}).get("market_cap", 0.0)

        total_cap = sum(caps.values())
        if total_cap == 0:
            return self._allocate_equal_weight(asset_classes, constraints)

        return {ac: cap / total_cap for ac, cap in caps.items()}

    def _allocate_risk_parity(
        self,
        asset_classes: list[AssetClass],
        asset_data: dict[AssetClass, dict[str, Any]],
        constraints: dict[AssetClass, dict[str, Any]],
    ) -> dict[AssetClass, float]:
        """Risk parity allocation — weights inversely proportional to volatility."""
        vols = {}
        min_vol = float("inf")
        for ac in asset_classes:
            if constraints.get(ac, {}).get("excluded", False):
                vols[ac] = 0.0
                continue
            v = asset_data.get(ac, {}).get("volatility", 0.15)
            vols[ac] = max(v, 0.01)  # floor to avoid division by zero
            min_vol = min(min_vol, vols[ac])

        if min_vol == float("inf") or min_vol == 0:
            return self._allocate_equal_weight(asset_classes, constraints)

        inv_vols = {}
        for ac in asset_classes:
            if vols.get(ac, 0) > 0:
                inv_vols[ac] = 1.0 / vols[ac]
            else:
                inv_vols[ac] = 0.0

        total_inv = sum(inv_vols.values())
        if total_inv == 0:
            return self._allocate_equal_weight(asset_classes, constraints)

        weights = {ac: inv / total_inv for ac, inv in inv_vols.items()}

        # Apply min/max constraints
        for ac in asset_classes:
            min_w = constraints.get(ac, {}).get("min_weight", 0.0)
            max_w = constraints.get(ac, {}).get("max_weight", 1.0)
            w = weights.get(ac, 0.0)
            weights[ac] = max(min_w, min(w, max_w))

        # Renormalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights

    def _allocate_min_variance(
        self,
        asset_classes: list[AssetClass],
        asset_data: dict[AssetClass, dict[str, Any]],
        constraints: dict[AssetClass, dict[str, Any]],
    ) -> dict[AssetClass, float]:
        """Approximate minimum variance allocation using inverse volatility squared."""
        inv_var = {}
        for ac in asset_classes:
            if constraints.get(ac, {}).get("excluded", False):
                inv_var[ac] = 0.0
                continue
            vol = asset_data.get(ac, {}).get("volatility", 0.15)
            vol = max(vol, 0.01)
            inv_var[ac] = 1.0 / (vol**2)

        total = sum(inv_var.values())
        if total == 0:
            return self._allocate_equal_weight(asset_classes, constraints)

        weights = {ac: inv / total for ac, inv in inv_var.items()}

        for ac in asset_classes:
            max_w = constraints.get(ac, {}).get("max_weight", 1.0)
            weights[ac] = min(weights.get(ac, 0.0), max_w)

        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights

    def _allocate_momentum(
        self,
        asset_classes: list[AssetClass],
        asset_data: dict[AssetClass, dict[str, Any]],
        constraints: dict[AssetClass, dict[str, Any]],
    ) -> dict[AssetClass, float]:
        """Momentum-based allocation — overweight positive momentum assets."""
        scores = {}
        for ac in asset_classes:
            if constraints.get(ac, {}).get("excluded", False):
                scores[ac] = 0.0
                continue
            mom_3m = asset_data.get(ac, {}).get("momentum_3m", 0.0)
            mom_6m = asset_data.get(ac, {}).get("momentum_6m", 0.0)
            mom_12m = asset_data.get(ac, {}).get("momentum_12m", 0.0)
            # Weighted momentum score (higher weight on recent)
            score = 0.5 * mom_3m + 0.3 * mom_6m + 0.2 * mom_12m
            # Transform to positive weight through softmax-like adjustment
            scores[ac] = max(score, -0.5) + 0.5  # Shift to [0, inf)

        total = sum(scores.values())
        if total == 0:
            return self._allocate_equal_weight(asset_classes, constraints)

        weights = {ac: score / total for ac, score in scores.items()}
        return weights

    def _allocate_black_litterman(
        self,
        asset_classes: list[AssetClass],
        asset_data: dict[AssetClass, dict[str, Any]],
        views: Optional[dict[AssetClass, float]],
        constraints: dict[AssetClass, dict[str, Any]],
    ) -> dict[AssetClass, float]:
        """Black-Litterman allocation blending equilibrium returns with views.

        Simplified implementation: start with market-cap weights as equilibrium,
        tilt toward assets with positive views.
        """
        # Equilibrium = market-cap weights
        equilibrium = self._allocate_market_cap(asset_classes, asset_data, constraints)

        views = views or {}
        tau = 0.025  # uncertainty in equilibrium
        tilt_strength = 0.3  # how much to tilt toward views

        adjusted = {}
        for ac in asset_classes:
            eq_w = equilibrium.get(ac, 0.0)
            view = views.get(ac, 0.0)  # expected excess return

            # Tilt: positive view → increase weight, negative view → decrease
            tilt = tilt_strength * view * tau
            adjusted[ac] = max(0.0, eq_w * (1.0 + tilt))

        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted

    def _allocate_adaptive(
        self,
        asset_classes: list[AssetClass],
        asset_data: dict[AssetClass, dict[str, Any]],
        constraints: dict[AssetClass, dict[str, Any]],
    ) -> dict[AssetClass, float]:
        """Adaptive allocation blending multiple signals based on regime.

        Uses a weighted blend of risk parity (50%), momentum (30%),
        and minimum variance (20%) signals, adjusted by current regime.
        """
        rp = self._allocate_risk_parity(asset_classes, asset_data, constraints)
        mom = self._allocate_momentum(asset_classes, asset_data, constraints)
        mv = self._allocate_min_variance(asset_classes, asset_data, constraints)

        # Regime-dependent blend weights
        regime = asset_data.get("_regime", {}).get("value", "normal")
        BLEND = {
            "low_vol": (0.2, 0.5, 0.3),  # (rp, mom, mv) — more momentum in low vol
            "normal": (0.5, 0.3, 0.2),
            "high_vol": (0.4, 0.2, 0.4),  # more min-var in high vol
            "crisis": (0.3, 0.1, 0.6),  # defensive in crisis
        }
        w_rp, w_mom, w_mv = BLEND.get(regime, BLEND["normal"])

        blended = {}
        for ac in asset_classes:
            blended[ac] = w_rp * rp.get(ac, 0.0) + w_mom * mom.get(ac, 0.0) + w_mv * mv.get(ac, 0.0)

        total = sum(blended.values())
        if total > 0:
            blended = {k: v / total for k, v in blended.items()}

        return blended

    # ------------------------------------------------------------------
    # Portfolio Estimators
    # ------------------------------------------------------------------

    def _estimate_portfolio_metrics(
        self,
        allocations: list[AssetAllocation],
        asset_data: dict[AssetClass, dict[str, Any]],
    ) -> tuple[float, float]:
        """Estimate expected return and volatility from allocations."""
        exp_ret = 0.0
        exp_var = 0.0

        for a in allocations:
            data = asset_data.get(a.asset_class, {})
            ret = data.get("expected_return", 0.06)
            vol = data.get("volatility", 0.15)
            w = a.target_weight
            exp_ret += w * ret
            exp_var += w * w * vol * vol

        exp_vol = exp_var**0.5
        return exp_ret, exp_vol

    def _compute_diversification_ratio(self, allocations: list[AssetAllocation]) -> float:
        """Compute diversification ratio — higher = more diversified.

        Ratio = weighted_avg_vol / portfolio_vol, clamped to [0,1].
        """
        weights = [a.target_weight for a in allocations]
        vols = [0.15 for _ in allocations]  # default vol

        avg_vol = sum(w * v for w, v in zip(weights, vols))
        port_vol = (sum(w * w * v * v for w, v in zip(weights, vols))) ** 0.5

        if port_vol == 0:
            return 1.0

        ratio = avg_vol / port_vol
        # Normalize to [0, 1] — typical range is ~1.0–3.0
        normalized = min(1.0, (ratio - 1.0) / 2.0)
        return max(0.0, normalized)

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_allocate(
        self,
        asset_classes: Optional[list[AssetClass]] = None,
    ) -> dict[str, Any]:
        """Quick default allocation without detailed data.

        Args:
            asset_classes: Subset of asset classes (defaults to all).

        Returns:
            Dict with strategy, weights, and summary metrics.
        """
        asset_classes = asset_classes or list(AssetClass)
        result = self.allocate(asset_data={})
        return {
            "strategy": result.strategy.value,
            "horizon": result.horizon.value,
            "risk_tolerance": result.risk_tolerance.value,
            "weights": result.to_dict(),
            "sharpe_ratio": result.sharpe_ratio,
            "diversification_ratio": result.diversification_ratio,
        }

    def last_result(self) -> Optional[AllocationResult]:
        """Return the most recent allocation result."""
        return self.history[-1] if self.history else None

    def clear(self) -> None:
        """Reset allocation history."""
        self.history.clear()
