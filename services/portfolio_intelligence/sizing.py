"""AI Position Sizing Engine — risk-based position size calculation.

Determines optimal position sizes using multiple methodologies including
Kelly criterion, fixed fractional, volatility targeting, equal risk contribution,
and optimal-f approaches with configurable constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SizingMethod(str, Enum):
    """Position sizing methodologies."""

    FIXED_FRACTION = "fixed_fraction"
    KELLY_CRITERION = "kelly"
    VOLATILITY_TARGET = "volatility_target"
    EQUAL_RISK = "equal_risk"
    OPTIMAL_F = "optimal_f"
    RISK_BUDGET = "risk_budget"


class SizingPriority(str, Enum):
    """Priority rule when sizing constraints conflict."""

    RISK_FIRST = "risk_first"
    RETURN_FIRST = "return_first"
    BALANCED = "balanced"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class PositionSize:
    """Position size result for a single asset.

    Attributes:
        symbol: Asset identifier.
        target_size_pct: Target position size as percentage of portfolio (0–1).
        capital_allocation: Absolute capital allocated.
        expected_risk_contribution: Risk contribution in portfolio risk units.
        stop_loss_pct: Recommended stop-loss level.
        take_profit_pct: Recommended take-profit level.
        method: Sizing method used.
        constraints_applied: Whether position constraints were active.
    """

    symbol: str
    target_size_pct: float
    capital_allocation: float = 0.0
    expected_risk_contribution: float = 0.0
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    method: SizingMethod = SizingMethod.FIXED_FRACTION
    constraints_applied: bool = False

    def validate(self, max_position: float = 0.25) -> bool:
        """Check if position size respects the maximum limit."""
        return self.target_size_pct <= max_position


@dataclass
class SizingResult:
    """Aggregated position sizing result.

    Attributes:
        positions: List of individual position sizes.
        total_allocation: Sum of all position target sizes (should be ≤ 1.0).
        remaining_capital: Unallocated capital as percentage.
        method: Primary sizing method.
        priority: Constraint resolution priority.
        concentration_ratio: Top-5 position concentration (0–1).
        risk_utilization: Total risk budget consumed.
        timestamp: When sizing was computed.
    """

    positions: list[PositionSize]
    total_allocation: float = 0.0
    remaining_capital: float = 0.0
    method: SizingMethod = SizingMethod.FIXED_FRACTION
    priority: SizingPriority = SizingPriority.BALANCED
    concentration_ratio: float = 0.0
    risk_utilization: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def position_count(self) -> int:
        """Number of active positions (size > 0)."""
        return sum(1 for p in self.positions if p.target_size_pct > 0)

    @property
    def is_fully_allocated(self) -> bool:
        """Whether portfolio is fully allocated."""
        return self.remaining_capital <= 0.01

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "positions": [
                {
                    "symbol": p.symbol,
                    "target_size_pct": p.target_size_pct,
                    "capital_allocation": p.capital_allocation,
                    "stop_loss_pct": p.stop_loss_pct,
                    "method": p.method.value,
                }
                for p in self.positions
            ],
            "total_allocation": self.total_allocation,
            "remaining_capital": self.remaining_capital,
            "method": self.method.value,
            "concentration_ratio": self.concentration_ratio,
            "risk_utilization": self.risk_utilization,
        }


# ---------------------------------------------------------------------------
# PositionSizingEngine
# ---------------------------------------------------------------------------


class PositionSizingEngine:
    """AI position sizing engine using risk-based methodologies.

    Supports Kelly, fixed fractional, volatility targeting, equal risk,
    and optimal-f approaches. Applies sanity checks: max position, max
    leverage, liquidity constraints, correlation penalties.

    Attributes:
        method: Default sizing method.
        priority: Default constraint resolution priority.
        max_position: Maximum single position as fraction (default 0.25).
        max_leverage: Maximum portfolio leverage (default 1.0).
        history: Past sizing results.
    """

    DEFAULT_PARAMS: dict[str, Any] = {
        "max_position": 0.25,
        "max_leverage": 1.0,
        "min_position": 0.005,
        "kelly_fraction": 0.5,  # half-Kelly default
        "vol_target": 0.15,  # 15% annual vol target
        "risk_free_rate": 0.03,
        "liquidity_multiplier": 1.0,
    }

    def __init__(
        self,
        method: SizingMethod = SizingMethod.FIXED_FRACTION,
        priority: SizingPriority = SizingPriority.BALANCED,
        params: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize the sizing engine.

        Args:
            method: Default sizing method.
            priority: Default constraint priority.
            params: Override default parameters.
        """
        self.method = method
        self.priority = priority
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}
        self.history: list[SizingResult] = []

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------

    def calculate(
        self,
        assets: list[dict[str, Any]],
        portfolio_value: float = 1_000_000.0,
        method: Optional[SizingMethod] = None,
        constraints: Optional[dict[str, Any]] = None,
    ) -> SizingResult:
        """Calculate optimal position sizes for a set of assets.

        Args:
            assets: List of dicts with keys: symbol, win_rate, avg_win,
                    avg_loss, volatility, correlation, liquidity_score.
            portfolio_value: Total portfolio value.
            method: Override default sizing method.
            constraints: Per-asset constraints and global limits.

        Returns:
            SizingResult with position sizes and risk metrics.
        """
        method = method or self.method
        constraints = constraints or {}

        max_pos = constraints.get("max_position", self.params["max_position"])
        max_lev = constraints.get("max_leverage", self.params["max_leverage"])

        # Route to specific method
        if method == SizingMethod.FIXED_FRACTION:
            positions = self._size_fixed_fraction(assets, portfolio_value, constraints)
        elif method == SizingMethod.KELLY_CRITERION:
            positions = self._size_kelly(assets, portfolio_value, constraints)
        elif method == SizingMethod.VOLATILITY_TARGET:
            positions = self._size_volatility_target(assets, portfolio_value, constraints)
        elif method == SizingMethod.EQUAL_RISK:
            positions = self._size_equal_risk(assets, portfolio_value, constraints)
        elif method == SizingMethod.OPTIMAL_F:
            positions = self._size_optimal_f(assets, portfolio_value, constraints)
        elif method == SizingMethod.RISK_BUDGET:
            positions = self._size_risk_budget(assets, portfolio_value, constraints)
        else:
            positions = self._size_fixed_fraction(assets, portfolio_value, constraints)

        # Apply global constraints (position caps, leverage limit)
        positions = self._apply_global_constraints(positions, max_pos, max_lev)

        # Apply correlation penalty and liquidity adjustment
        positions = self._apply_correlation_penalty(positions, assets)
        positions = self._apply_liquidity_adjustment(positions, assets)

        total = sum(p.target_size_pct for p in positions)

        # Concentration: sum of squared weights (HHI)
        hhi = sum(p.target_size_pct**2 for p in positions)
        # Normalize: pure equal-weight → 1/n, max concentration → 1.0
        n = max(len(positions), 1)
        conc_ratio = max(0.0, min(1.0, (hhi * n - 1.0) / (n - 1.0))) if n > 1 else 1.0

        # Risk utilization: total allocation / max allowed
        risk_util = min(1.0, total / max_lev) if max_lev > 0 else 1.0

        result = SizingResult(
            positions=sorted(positions, key=lambda p: p.target_size_pct, reverse=True),
            total_allocation=total,
            remaining_capital=max(0.0, max_lev - total),
            method=method,
            priority=self.priority,
            concentration_ratio=conc_ratio,
            risk_utilization=risk_util,
        )

        self.history.append(result)
        return result

    # ------------------------------------------------------------------
    # Sizing Method Implementations
    # ------------------------------------------------------------------

    def _size_fixed_fraction(
        self,
        assets: list[dict[str, Any]],
        portfolio_value: float,
        constraints: dict[str, Any],
    ) -> list[PositionSize]:
        """Fixed fractional sizing: equal allocation to all assets."""
        n = max(len(assets), 1)
        base_weight = 1.0 / n
        risk_per_trade = constraints.get("risk_per_trade", 0.02)

        results = []
        for a in assets:
            symbol = a["symbol"]
            size = base_weight
            stop_loss = a.get("stop_loss", 0.05)
            results.append(
                PositionSize(
                    symbol=symbol,
                    target_size_pct=size,
                    capital_allocation=size * portfolio_value,
                    expected_risk_contribution=size * risk_per_trade,
                    stop_loss_pct=stop_loss,
                    method=SizingMethod.FIXED_FRACTION,
                )
            )
        return results

    def _size_kelly(
        self,
        assets: list[dict[str, Any]],
        portfolio_value: float,
        constraints: dict[str, Any],
    ) -> list[PositionSize]:
        """Kelly criterion sizing: f* = win_rate - (loss_rate / win_loss_ratio)."""
        kelly_frac = constraints.get("kelly_fraction", self.params["kelly_fraction"])

        # Compute raw Kelly fractions
        kelly_sizes = {}
        for a in assets:
            win_rate = a.get("win_rate", 0.5)
            avg_win = a.get("avg_win", 0.02)
            avg_loss = a.get("avg_loss", 0.02)
            ratio = avg_win / max(avg_loss, 0.0001)
            f_star = (win_rate - (1.0 - win_rate) / max(ratio, 1.0)) * kelly_frac
            f_star = max(0.0, min(0.3, f_star))  # cap at 30%
            kelly_sizes[a["symbol"]] = f_star

        # Scale Kelly sizes so they sum to ≤ 1.0
        total_kelly = sum(kelly_sizes.values())
        if total_kelly == 0:
            return self._size_fixed_fraction(assets, portfolio_value, constraints)

        results = []
        for a in assets:
            symbol = a["symbol"]
            f = kelly_sizes[symbol]
            size = f / total_kelly if total_kelly > 1.0 else f
            results.append(
                PositionSize(
                    symbol=symbol,
                    target_size_pct=size,
                    capital_allocation=size * portfolio_value,
                    expected_risk_contribution=size * a.get("volatility", 0.15),
                    stop_loss_pct=a.get("avg_loss", 0.05),
                    method=SizingMethod.KELLY_CRITERION,
                )
            )
        return results

    def _size_volatility_target(
        self,
        assets: list[dict[str, Any]],
        portfolio_value: float,
        constraints: dict[str, Any],
    ) -> list[PositionSize]:
        """Volatility targeting: allocate inversely to individual vol."""
        vol_target = constraints.get("vol_target", self.params["vol_target"])

        inv_vols = {}
        for a in assets:
            vol = max(a.get("volatility", 0.15), 0.01)
            inv_vols[a["symbol"]] = 1.0 / vol

        total = sum(inv_vols.values())
        if total == 0:
            return self._size_fixed_fraction(assets, portfolio_value, constraints)

        # Scale to meet vol target
        results = []
        for a in assets:
            symbol = a["symbol"]
            raw_weight = inv_vols[symbol] / total
            vol = a.get("volatility", 0.15)
            # Adjust position to match vol target
            size = raw_weight * (vol_target / max(vol, 0.01))
            size = min(size, 0.25)
            results.append(
                PositionSize(
                    symbol=symbol,
                    target_size_pct=size,
                    capital_allocation=size * portfolio_value,
                    expected_risk_contribution=size * vol,
                    stop_loss_pct=2.0 * vol,  # 2-sigma stop
                    method=SizingMethod.VOLATILITY_TARGET,
                )
            )
        return results

    def _size_equal_risk(
        self,
        assets: list[dict[str, Any]],
        portfolio_value: float,
        constraints: dict[str, Any],
    ) -> list[PositionSize]:
        """Equal risk contribution: each position contributes equal risk."""
        risk_per_unit = {}
        for a in assets:
            vol = max(a.get("volatility", 0.15), 0.01)
            risk_per_unit[a["symbol"]] = vol

        inv_risk = {k: 1.0 / max(v, 0.001) for k, v in risk_per_unit.items()}
        total = sum(inv_risk.values())

        results = []
        for a in assets:
            symbol = a["symbol"]
            size = inv_risk[symbol] / max(total, 1.0)
            results.append(
                PositionSize(
                    symbol=symbol,
                    target_size_pct=size,
                    capital_allocation=size * portfolio_value,
                    expected_risk_contribution=size * risk_per_unit[symbol],
                    stop_loss_pct=1.5 * risk_per_unit[symbol],
                    method=SizingMethod.EQUAL_RISK,
                )
            )
        return results

    def _size_optimal_f(
        self,
        assets: list[dict[str, Any]],
        portfolio_value: float,
        constraints: dict[str, Any],
    ) -> list[PositionSize]:
        """Optimal-f sizing: maximize geometric growth with drawdown constraints."""
        max_dd = constraints.get("max_drawdown", 0.20)

        results = []
        for a in assets:
            symbol = a["symbol"]
            win_rate = a.get("win_rate", 0.5)
            avg_win = a.get("avg_win", 0.02)
            avg_loss = a.get("avg_loss", 0.02)
            vol = a.get("volatility", 0.15)

            # Basic optimal-f approximation
            profitability = win_rate * avg_win - (1.0 - win_rate) * avg_loss
            # Cap by max drawdown / volatility
            f = min(profitability / max(vol**2, 0.0001), max_dd / max(vol, 0.01))
            f = max(0.0, min(0.25, f))

            results.append(
                PositionSize(
                    symbol=symbol,
                    target_size_pct=f,
                    capital_allocation=f * portfolio_value,
                    expected_risk_contribution=f * vol,
                    stop_loss_pct=max_dd / 2.0,
                    method=SizingMethod.OPTIMAL_F,
                )
            )
        return results

    def _size_risk_budget(
        self,
        assets: list[dict[str, Any]],
        portfolio_value: float,
        constraints: dict[str, Any],
    ) -> list[PositionSize]:
        """Risk budget sizing: allocate based on assigned risk budget per asset."""
        budgets = constraints.get("risk_budgets", {})
        default_budget = 1.0 / max(len(assets), 1)

        results = []
        for a in assets:
            symbol = a["symbol"]
            budget = budgets.get(symbol, default_budget)
            vol = max(a.get("volatility", 0.15), 0.01)
            # Size = budget / volatility (higher vol → smaller size for same risk)
            size = budget / vol
            results.append(
                PositionSize(
                    symbol=symbol,
                    target_size_pct=size,
                    capital_allocation=size * portfolio_value,
                    expected_risk_contribution=budget * vol,
                    stop_loss_pct=2.0 * vol,
                    method=SizingMethod.RISK_BUDGET,
                )
            )

        # Normalize
        total = sum(p.target_size_pct for p in results)
        if total > 0:
            for p in results:
                p.target_size_pct /= total
                p.capital_allocation = p.target_size_pct * portfolio_value

        return results

    # ------------------------------------------------------------------
    # Constraint Application
    # ------------------------------------------------------------------

    def _apply_global_constraints(
        self,
        positions: list[PositionSize],
        max_position: float,
        max_leverage: float,
    ) -> list[PositionSize]:
        """Cap individual positions and total leverage."""
        # Cap individual positions
        for p in positions:
            if p.target_size_pct > max_position:
                p.target_size_pct = max_position
                p.capital_allocation = max_position * (
                    p.capital_allocation / max(p.target_size_pct, 0.0001) if p.target_size_pct > 0 else 1_000_000.0
                )
                p.constraints_applied = True

        # Cap total to max leverage
        total = sum(p.target_size_pct for p in positions)
        if total > max_leverage and total > 0:
            scale = max_leverage / total
            for p in positions:
                p.target_size_pct *= scale
                p.capital_allocation *= scale
                p.constraints_applied = True

        return positions

    def _apply_correlation_penalty(
        self,
        positions: list[PositionSize],
        assets: list[dict[str, Any]],
    ) -> list[PositionSize]:
        """Reduce position sizes for highly correlated assets."""
        symbols = {p.symbol: p for p in positions}
        corr_data = {a["symbol"]: a.get("correlation", 0.0) for a in assets}

        for p in positions:
            avg_corr = 0.0
            count = 0
            for other_sym, corr in corr_data.items():
                if other_sym != p.symbol:
                    if isinstance(corr, dict):  # correlation matrix row
                        avg_corr += abs(corr.get(p.symbol, 0.0))
                    else:
                        avg_corr += abs(corr)
                    count += 1
            if count > 0:
                avg_corr /= count
                # Reduce size if avg correlation > 0.5
                if avg_corr > 0.5:
                    penalty = 1.0 - (avg_corr - 0.5) * 0.5  # max 25% reduction
                    p.target_size_pct *= max(0.5, penalty)
                    p.capital_allocation *= max(0.5, penalty)

        return positions

    def _apply_liquidity_adjustment(
        self,
        positions: list[PositionSize],
        assets: list[dict[str, Any]],
    ) -> list[PositionSize]:
        """Adjust sizes based on liquidity scores."""
        liq_data = {a["symbol"]: a.get("liquidity_score", 1.0) for a in assets}

        for p in positions:
            liq = liq_data.get(p.symbol, 1.0)
            if liq < 0.5:
                multiplier = max(0.3, liq / 0.5)
                p.target_size_pct *= multiplier
                p.capital_allocation *= multiplier

        return positions

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_size(
        self,
        symbols: list[str],
        portfolio_value: float = 1_000_000.0,
    ) -> dict[str, Any]:
        """Quick sizing with default parameters.

        Args:
            symbols: List of asset symbols.
            portfolio_value: Total portfolio value.

        Returns:
            Dict with position sizes and summary metrics.
        """
        assets = [
            {
                "symbol": s,
                "win_rate": 0.5,
                "avg_win": 0.02,
                "avg_loss": 0.02,
                "volatility": 0.15,
                "correlation": 0.0,
                "liquidity_score": 1.0,
            }
            for s in symbols
        ]
        result = self.calculate(assets, portfolio_value)
        return {
            "positions": {
                p.symbol: {
                    "size_pct": round(p.target_size_pct, 4),
                    "capital": round(p.capital_allocation, 2),
                }
                for p in result.positions
            },
            "total_allocation": round(result.total_allocation, 4),
            "remaining_capital": round(result.remaining_capital, 4),
            "concentration_ratio": round(result.concentration_ratio, 4),
        }

    def last_result(self) -> Optional[SizingResult]:
        """Return the most recent sizing result."""
        return self.history[-1] if self.history else None

    def clear(self) -> None:
        """Reset sizing history."""
        self.history.clear()
