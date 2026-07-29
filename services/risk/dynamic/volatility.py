"""Dynamic Volatility Targeting - position sizing based on volatility regime."""

from __future__ import annotations

from typing import Dict, List, Optional
import math


class VolatilityTargeter:
    """Volatility Targeting Engine.

    Implements target volatility position sizing.

    Formula:
        Position Size = (Target Vol / Current Vol) * Current Position

    Example:
        Fund target: 15% annual vol
        Current portfolio vol: 25%
        → Position multiplier = 15% / 25% = 0.6
        → Reduce positions to 60%

    This automatically reduces risk in high-vol environments
    and increases allocation when volatility is low.
    """

    def __init__(
        self,
        target_volatility: float = 0.15,
        max_leverage: float = 1.5,
        min_leverage: float = 0.20,
        smoothing_window: int = 5,
    ):
        self.target_volatility = target_volatility
        self.max_leverage = max_leverage
        self.min_leverage = min_leverage
        self.smoothing_window = smoothing_window
        self._vol_history: List[float] = []

    def compute_adjustment(
        self,
        current_volatility: float,
        current_position: float,
        method: str = "simple",
    ) -> Dict[str, float]:
        """Compute position adjustment to achieve target volatility.

        Args:
            current_volatility: Current realized or forecast volatility (annualized).
            current_position: Current position size or exposure.

        Returns:
            Dict with adjustment details.
        """
        # Record volatility
        self._vol_history.append(current_volatility)
        if len(self._vol_history) > self.smoothing_window:
            self._vol_history.pop(0)

        # Smoothed volatility
        smoothed_vol = self._get_smoothed_volatility()

        # Compute scaling factor
        if method == "simple":
            scale = self.target_volatility / max(smoothed_vol, 0.001)
        elif method == "kelly":
            # Kelly-inspired: scale proportionally but more conservative
            sharpe_estimate = 0.5 / max(smoothed_vol, 0.001)
            scale = sharpe_estimate * (self.target_volatility / max(smoothed_vol, 0.001))
        elif method == "adaptive":
            # Adaptive: use recent vol trend
            trend = self._compute_vol_trend()
            base_scale = self.target_volatility / max(smoothed_vol, 0.001)
            scale = base_scale * (1.0 - trend * 0.5)  # Reduce more if vol trending up
        else:
            raise ValueError(f"Unknown method: {method}")

        # Clamp to leverage limits
        scale = max(self.min_leverage, min(self.max_leverage, scale))

        target_position = current_position * scale
        adjustment_pct = (scale - 1.0) * 100

        return {
            "method": method,
            "target_volatility": self.target_volatility,
            "current_volatility": round(current_volatility, 4),
            "smoothed_volatility": round(smoothed_vol, 4),
            "scale_factor": round(scale, 4),
            "current_position": current_position,
            "target_position": round(target_position, 2),
            "adjustment_pct": round(adjustment_pct, 2),
            "action": self._get_action_description(scale),
            "leverage_used": round(scale, 4),
        }

    def compute_multi_asset_adjustment(
        self,
        positions: Dict[str, float],
        volatilities: Dict[str, float],
        correlations: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> Dict:
        """Compute volatility-targeted adjustments for multiple assets.

        Args:
            positions: Asset -> position size dict.
            volatilities: Asset -> annualized volatility dict.
            correlations: Optional asset correlation matrix.

        Returns:
            Dict with per-asset and portfolio adjustments.
        """
        total_position = sum(positions.values())

        # Portfolio volatility (weighted average, simplified)
        if positions:
            weights = {k: v / total_position for k, v in positions.items() if total_position > 0}
            portfolio_vol = math.sqrt(
                sum(weights.get(k, 0) ** 2 * volatilities.get(k, 0) ** 2
                    for k in positions)
            )
        else:
            portfolio_vol = 0.0

        # Overall scale factor
        scale = self.target_volatility / max(portfolio_vol, 0.001)
        scale = max(self.min_leverage, min(self.max_leverage, scale))

        # Per-asset adjustments
        adjustments = {}
        for asset, position in positions.items():
            asset_vol = volatilities.get(asset, 0.15)
            # Individual scale based on asset vol relative to portfolio
            individual_scale = self.target_volatility / max(asset_vol, 0.001)
            individual_scale = max(self.min_leverage, min(self.max_leverage, individual_scale))
            target = position * individual_scale
            adjustments[asset] = {
                "current": position,
                "target": round(target, 2),
                "change_pct": round((individual_scale - 1.0) * 100, 2),
                "asset_vol": asset_vol,
            }

        return {
            "portfolio_volatility": round(portfolio_vol, 4),
            "portfolio_scale": round(scale, 4),
            "target_volatility": self.target_volatility,
            "adjustments": adjustments,
            "action": self._get_action_description(scale),
        }

    def get_volatility_regime(self, current_vol: float) -> Dict[str, any]:
        """Determine the current volatility regime.

        Args:
            current_vol: Current annualized volatility.

        Returns:
            Dict with regime classification.
        """
        if current_vol < self.target_volatility * 0.7:
            regime = "LOW_VOL"
            action = "Increase positions opportunistically"
        elif current_vol < self.target_volatility * 1.3:
            regime = "TARGET"
            action = "Maintain current sizing"
        elif current_vol < self.target_volatility * 2.5:
            regime = "HIGH_VOL"
            action = "Reduce positions to target volatility"
        else:
            regime = "EXTREME_VOL"
            action = "Significantly reduce or exit positions"

        return {
            "regime": regime,
            "current_vol": round(current_vol, 4),
            "target_vol": self.target_volatility,
            "ratio": round(current_vol / max(self.target_volatility, 0.001), 2),
            "recommended_action": action,
        }

    def forecast_volatility(
        self,
        returns: List[float],
        method: str = "ewma",
        decay: float = 0.94,
    ) -> float:
        """Forecast forward volatility.

        Args:
            returns: Historical return series.
            method: "ewma", "garch_approx", or "simple".
            decay: EWMA decay factor (default 0.94).

        Returns:
            Forecasted annualized volatility.
        """
        if method == "simple":
            return self._compute_volatility(returns)
        elif method == "ewma":
            return self._ewma_volatility(returns, decay)
        elif method == "garch_approx":
            return self._garch_approx(returns)
        else:
            raise ValueError(f"Unknown forecast method: {method}")

    # ---- Internal helpers ----

    def _get_smoothed_volatility(self) -> float:
        if not self._vol_history:
            return self.target_volatility
        return sum(self._vol_history) / len(self._vol_history)

    def _compute_vol_trend(self) -> float:
        if len(self._vol_history) < 2:
            return 0.0
        # Simple linear trend
        n = len(self._vol_history)
        x_mean = (n - 1) / 2
        y_mean = sum(self._vol_history) / n
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(self._vol_history))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        return numerator / denominator if denominator > 0 else 0.0

    def _get_action_description(self, scale: float) -> str:
        if scale > 1.05:
            return "INCREASE_POSITION"
        elif scale < 0.95:
            return "REDUCE_POSITION"
        return "HOLD"

    def _compute_volatility(self, returns: List[float]) -> float:
        if len(returns) < 2:
            return 0.0
        n = len(returns)
        mean = sum(returns) / n
        daily_var = sum((r - mean) ** 2 for r in returns) / (n - 1)
        daily_vol = math.sqrt(daily_var)
        return daily_vol * math.sqrt(252)

    def _ewma_volatility(self, returns: List[float], decay: float) -> float:
        """EWMA volatility estimation."""
        if not returns:
            return 0.0
        variance = returns[0] ** 2
        for r in returns[1:]:
            variance = decay * variance + (1 - decay) * r ** 2
        return math.sqrt(variance) * math.sqrt(252)

    def _garch_approx(self, returns: List[float]) -> float:
        """Simple GARCH(1,1) approximation."""
        if len(returns) < 2:
            return 0.0
        # Use EWMA as GARCH approximation
        return self._ewma_volatility(returns, 0.94)
