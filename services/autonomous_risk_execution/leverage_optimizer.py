"""
Leverage Optimizer — controls and optimizes portfolio leverage.

Manages:
    - Gross leverage (long + short)
    - Net leverage (long - short)
    - Long-only leverage
    - Short-side leverage
    - Dynamic leverage based on regime and volatility
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class LeverageConstraints:
    """Leverage constraint parameters."""
    max_gross_leverage: float = 3.0
    max_net_leverage: float = 1.5
    max_long_leverage: float = 2.0
    max_short_leverage: float = 1.0
    target_leverage: float = 1.0
    min_leverage: float = 0.10
    dynamic_scaling: bool = True


@dataclass
class LeverageProfile:
    """Current leverage profile."""
    gross_leverage: float = 1.0
    net_leverage: float = 1.0
    long_leverage: float = 1.0
    short_leverage: float = 0.0
    effective_leverage: float = 1.0


@dataclass
class LeverageResult:
    """Result of leverage optimization."""
    id: str = field(default_factory=lambda: str(uuid4()))
    original: LeverageProfile = field(default_factory=LeverageProfile)
    optimized: LeverageProfile = field(default_factory=LeverageProfile)
    scaling_factor: float = 1.0
    adjustments: list[dict] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class LeverageOptimizer:
    """
    Autonomous leverage optimization.

    Core formula:
        target_leverage = base_leverage * regime_scale * volatility_scale * drawdown_scale

    Safety: Leverage is ALWAYS clamped by explicit max constraints regardless of regime.
    """

    def __init__(self, constraints: Optional[LeverageConstraints] = None) -> None:
        self._constraints = constraints or LeverageConstraints()
        self._last_result: Optional[LeverageResult] = None

    async def optimize(
        self,
        current: LeverageProfile,
        regime: str = "NORMAL",
        volatility: float = 0.15,
        drawdown: float = 0.0,
    ) -> LeverageResult:
        """Optimize leverage profile."""
        result = LeverageResult(original=current)

        # Compute dynamic target leverage
        target = self._constraints.target_leverage
        if self._constraints.dynamic_scaling:
            target *= self._regime_scale(regime)
            target *= self._volatility_scale(volatility)
            target *= self._drawdown_scale(drawdown)
            target = max(self._constraints.min_leverage, min(
                target, self._constraints.max_gross_leverage
            ))

        # Clamp each dimension
        adjusted = LeverageProfile(
            gross_leverage=min(current.gross_leverage, self._constraints.max_gross_leverage),
            net_leverage=max(
                -self._constraints.max_net_leverage,
                min(current.net_leverage, self._constraints.max_net_leverage),
            ),
            long_leverage=min(current.long_leverage, self._constraints.max_long_leverage),
            short_leverage=min(current.short_leverage, self._constraints.max_short_leverage),
            effective_leverage=target,
        )

        # Scale to target
        if current.gross_leverage > 0 and target < current.gross_leverage:
            scale = target / current.gross_leverage
            result.scaling_factor = scale
            adjusted.gross_leverage = target
            adjusted.long_leverage *= scale
            adjusted.short_leverage *= scale
            adjusted.net_leverage = adjusted.long_leverage - adjusted.short_leverage
            result.adjustments.append({
                "type": "leverage_scale", "from": current.gross_leverage,
                "to": target, "factor": scale,
            })

        # Enforce net leverage cap after scaling
        if abs(adjusted.net_leverage) > self._constraints.max_net_leverage:
            long_over = max(0, adjusted.long_leverage - self._constraints.max_long_leverage)
            short_over = max(0, adjusted.short_leverage - self._constraints.max_short_leverage)
            adjusted.long_leverage -= long_over
            adjusted.short_leverage -= short_over
            adjusted.net_leverage = adjusted.long_leverage - adjusted.short_leverage
            adjusted.gross_leverage = adjusted.long_leverage + adjusted.short_leverage
            result.adjustments.append({
                "type": "net_leverage_cap", "net": adjusted.net_leverage,
            })

        result.optimized = adjusted
        result.timestamp = datetime.now()
        self._last_result = result

        logger.debug(
            "Leverage: gross=%.2f→%.2f net=%.2f target=%.2f scale=%.2f",
            current.gross_leverage, adjusted.gross_leverage,
            adjusted.net_leverage, target, result.scaling_factor,
        )
        return result

    # ── Scaling Functions ──────────────────────────────────────

    def _regime_scale(self, regime: str) -> float:
        scales = {
            "NORMAL": 1.00, "TRENDING": 1.10, "MEAN_REVERTING": 0.85,
            "HIGH_VOL": 0.55, "RISK_OFF": 0.30, "CRISIS": 0.10,
        }
        return scales.get(regime, 0.50)

    def _volatility_scale(self, vol: float, target: float = 0.15) -> float:
        if vol <= 0:
            return 1.0
        return max(0.20, min(target / vol, 1.5))

    def _drawdown_scale(self, dd: float) -> float:
        if dd <= 0.03:
            return 1.00
        elif dd <= 0.06:
            return 0.80
        elif dd <= 0.10:
            return 0.55
        else:
            return 0.25

    def compute_profile(self, positions: dict[str, float]) -> LeverageProfile:
        """Compute leverage profile from positions."""
        long_exp = sum(v for v in positions.values() if v > 0)
        short_exp = sum(abs(v) for v in positions.values() if v < 0)
        return LeverageProfile(
            gross_leverage=long_exp + short_exp,
            net_leverage=long_exp - short_exp,
            long_leverage=long_exp,
            short_leverage=short_exp,
            effective_leverage=long_exp + short_exp,
        )

    @property
    def last_result(self) -> Optional[LeverageResult]:
        return self._last_result
