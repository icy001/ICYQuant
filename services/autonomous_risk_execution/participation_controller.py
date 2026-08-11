"""
Participation Controller — manages participation rate (our volume / market volume).

Controls how aggressively orders participate in market volume:
    - Target participation rate (e.g. 5%, 10%, 15%)
    - Adaptive adjustment based on market conditions
    - Anti-gaming protection
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ParticipationConfig:
    """Participation rate configuration."""
    target_rate: float = 0.10
    max_rate: float = 0.20
    min_rate: float = 0.02
    adaptive: bool = True
    volume_lookback_seconds: int = 60


@dataclass
class ParticipationState:
    """Current participation state."""
    current_rate: float = 0.0
    rolling_volume: float = 0.0
    our_volume: float = 0.0
    market_volume: float = 0.0
    is_exceeding: bool = False
    adjusted_rate: float = 0.10


class ParticipationController:
    """
    Controls order participation rate relative to market volume.

    Adaptive adjustments:
        - If market volume increases → increase participation
        - If market volume decreases → decrease participation
        - If we exceed target → throttle
        - Anti-gaming: randomize around target ±10%
    """

    def __init__(self, config: Optional[ParticipationConfig] = None) -> None:
        self._config = config or ParticipationConfig()
        self._state = ParticipationState()
        self._history: list[ParticipationState] = []

    async def get_current_rate(
        self, our_volume: float, market_volume: float
    ) -> float:
        """Get current participation rate."""
        if market_volume <= 0:
            return 0.0
        return our_volume / market_volume

    async def compute_target(
        self,
        order_size: float,
        market_volume_per_second: float,
        time_horizon_seconds: int = 1800,
        spread_bps: float = 5.0,
        volatility: float = 0.15,
    ) -> float:
        """
        Compute optimal target participation rate.

        Lower rate for:
            - Higher spreads (don't chase)
            - Higher volatility (be careful)
            - Longer horizons (can be patient)

        Higher rate for:
            - Shorter horizons (need to complete)
            - High liquidity (can absorb)
        """
        target = self._config.target_rate

        if self._config.adaptive:
            # Adjust for spread
            if spread_bps > 15:
                target *= 0.70
            elif spread_bps < 3:
                target *= 1.10

            # Adjust for volatility
            if volatility > 0.30:
                target *= 0.60
            elif volatility < 0.10:
                target *= 1.05

            # Adjust for time pressure
            time_pressure = max(0, 1 - time_horizon_seconds / 3600)
            target *= 1.0 + time_pressure * 0.5

        # Clamp
        target = max(self._config.min_rate, min(target, self._config.max_rate))

        # Ensure order doesn't exceed max rate given volume
        vol_based_limit = order_size / max(market_volume_per_second * time_horizon_seconds, 1)
        target = min(target, vol_based_limit)

        return target

    async def update(
        self, our_volume: float, market_volume: float
    ) -> ParticipationState:
        """Update participation state."""
        rate = await self.get_current_rate(our_volume, market_volume)
        self._state.current_rate = rate
        self._state.our_volume += our_volume
        self._state.market_volume += market_volume
        self._state.is_exceeding = rate > self._config.max_rate

        # Throttle if exceeding
        if self._state.is_exceeding:
            self._state.adjusted_rate = self._config.max_rate * 0.80
        else:
            self._state.adjusted_rate = min(rate, self._config.target_rate)

        self._history.append(ParticipationState(
            current_rate=rate,
            our_volume=our_volume,
            market_volume=market_volume,
            adjusted_rate=self._state.adjusted_rate,
        ))

        if self._state.is_exceeding:
            logger.warning(
                "Participation %.1f%% exceeds max %.1f%%, throttling",
                rate * 100, self._config.max_rate * 100,
            )
        return self._state

    @property
    def state(self) -> ParticipationState:
        return self._state

    @property
    def target_rate(self) -> float:
        return self._config.target_rate

    def reset(self) -> None:
        """Reset participation tracking."""
        self._state = ParticipationState()
        self._history.clear()
