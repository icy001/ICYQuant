"""
Volatility Controller — dynamic position scaling based on volatility.

Monitors both portfolio-level and asset-level volatility to:
    - Target a stable volatility profile
    - Scale positions inversely with volatility spikes
    - Detect volatility regime changes
    - Trigger defensive modes during volatility explosions
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class VolatilityConfig:
    """Volatility control configuration."""
    target_portfolio_vol: float = 0.15
    max_portfolio_vol: float = 0.25
    vol_spike_threshold: float = 0.30  # Daily vol above this = spike
    vol_scaling_enabled: bool = True
    vol_lookback_days: int = 20
    min_vol_floor: float = 0.05
    max_vol_ceiling: float = 0.50
    spike_cooling_seconds: int = 300


@dataclass
class VolatilityState:
    """Current volatility state."""
    portfolio_vol: float = 0.15
    asset_vols: dict[str, float] = field(default_factory=dict)
    is_spike: bool = False
    vol_regime: str = "NORMAL"
    scaling_factor: float = 1.0
    vol_ratio: float = 1.0  # current_vol / target_vol


class VolatilityController:
    """
    Volatility-based position scaling.

    Core formula:
        scale = target_vol / max(current_vol, min_vol_floor)
        scale = clamp(scale, 0.20, 1.50)

    Volatility regimes:
        NORMAL: vol within 0.5x-2x target
        ELEVATED: vol 2x-3x target
        SPIKE: vol > 3x target or spike detected
    """

    def __init__(self, config: Optional[VolatilityConfig] = None) -> None:
        self._config = config or VolatilityConfig()
        self._state = VolatilityState()
        self._history: list[VolatilityState] = []

    def update(
        self,
        portfolio_vol: float,
        asset_vols: Optional[dict[str, float]] = None,
    ) -> VolatilityState:
        """Update volatility state."""
        self._state.portfolio_vol = portfolio_vol
        self._state.asset_vols = asset_vols or {}

        # Vol regime
        target = self._config.target_portfolio_vol
        ratio = portfolio_vol / max(target, 0.01)
        self._state.vol_ratio = ratio

        if portfolio_vol > self._config.vol_spike_threshold:
            self._state.is_spike = True
            self._state.vol_regime = "SPIKE"
        elif ratio > 2.0:
            self._state.vol_regime = "ELEVATED"
            self._state.is_spike = False
        else:
            self._state.vol_regime = "NORMAL"
            self._state.is_spike = False

        # Scaling factor
        if self._config.vol_scaling_enabled:
            safe_vol = max(portfolio_vol, self._config.min_vol_floor)
            scale = target / safe_vol
            self._state.scaling_factor = max(0.20, min(scale, 1.50))
        else:
            self._state.scaling_factor = 1.0

        self._history.append(self._state)
        if len(self._history) > 1000:
            self._history = self._history[-500:]

        logger.debug(
            "Vol: current=%.3f target=%.3f scale=%.3f regime=%s",
            portfolio_vol, target, self._state.scaling_factor,
            self._state.vol_regime,
        )
        return self._state

    def get_position_scale(self, asset: str) -> float:
        """Get position scaling factor for a specific asset."""
        asset_vol = self._state.asset_vols.get(asset, self._state.portfolio_vol)
        if asset_vol <= 0:
            return self._state.scaling_factor

        asset_target = self._config.target_portfolio_vol
        scale = asset_target / max(asset_vol, self._config.min_vol_floor)
        asset_scale = max(0.15, min(scale, 1.50))

        # Combine with portfolio scale
        return min(self._state.scaling_factor, asset_scale)

    def get_risk_scale(self) -> float:
        """Get overall risk scaling based on volatility regime."""
        regime_scales = {
            "NORMAL": 1.00,
            "ELEVATED": 0.70,
            "SPIKE": 0.40,
        }
        return regime_scales.get(self._state.vol_regime, 1.00)

    def is_spike_detected(self) -> bool:
        """Check if a volatility spike is currently detected."""
        return self._state.is_spike

    @property
    def state(self) -> VolatilityState:
        return self._state

    @property
    def scaling_factor(self) -> float:
        return self._state.scaling_factor

    def get_history(self, limit: int = 20) -> list[VolatilityState]:
        return self._history[-limit:]
