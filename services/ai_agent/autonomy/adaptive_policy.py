"""Adaptive Policy Engine — dynamically adjusts execution policies based on market regime and learned experience.

Pipeline:
    Market Regime + Learning Events -> AdaptivePolicy.adapt()
        -> Detect current market regime
        -> Select optimal policy profile
        -> Adjust execution parameters
        -> Apply policy to workflow
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    UNKNOWN = "unknown"


@dataclass
class PolicyProfile:
    """An adaptive policy profile for a market regime.

    Attributes:
        profile_id: Unique identifier.
        regime: Target market regime.
        position_sizing_multiplier: Scale positions (1.0 = normal).
        max_leverage: Maximum leverage allowed.
        execution_urgency: How quickly to execute (0.0-1.0).
        stop_loss_tightness: Stop-loss tightness multiplier.
        max_positions: Maximum number of positions.
        metadata: Additional profile data.
    """

    profile_id: str = ""
    regime: MarketRegime = MarketRegime.UNKNOWN
    position_sizing_multiplier: float = 1.0
    max_leverage: float = 1.0
    execution_urgency: float = 0.5
    stop_loss_tightness: float = 1.0
    max_positions: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)


class AdaptivePolicy:
    """Dynamically adjusts execution policies based on market regime.

    Selects optimal policy profiles for different market conditions
    and adapts based on learned experience from the feedback loop.

    Supports:
        - Market regime detection
        - Policy profile selection
        - Dynamic parameter adjustment
        - Experience-driven adaptation

    Usage:
        policy = AdaptivePolicy()
        await policy.initialize()
        profile = await policy.select_profile(market_regime=MarketRegime.BULL)
        await policy.adapt(learning_events)
    """

    def __init__(self) -> None:
        self._profiles: Dict[str, PolicyProfile] = {}
        self._active_regime: MarketRegime = MarketRegime.UNKNOWN
        self._counter: int = 0
        self._initialized: bool = False
        self._init_default_profiles()
        logger.info("AdaptivePolicy created")

    def _init_default_profiles(self) -> None:
        defaults = {
            MarketRegime.BULL: PolicyProfile(
                profile_id="default_bull",
                regime=MarketRegime.BULL,
                position_sizing_multiplier=1.2,
                max_leverage=1.0,
                execution_urgency=0.7,
                stop_loss_tightness=0.8,
                max_positions=30,
            ),
            MarketRegime.BEAR: PolicyProfile(
                profile_id="default_bear",
                regime=MarketRegime.BEAR,
                position_sizing_multiplier=0.5,
                max_leverage=0.5,
                execution_urgency=0.9,
                stop_loss_tightness=1.5,
                max_positions=15,
            ),
            MarketRegime.RANGING: PolicyProfile(
                profile_id="default_ranging",
                regime=MarketRegime.RANGING,
                position_sizing_multiplier=0.8,
                max_leverage=1.0,
                execution_urgency=0.5,
                stop_loss_tightness=1.0,
                max_positions=20,
            ),
            MarketRegime.HIGH_VOLATILITY: PolicyProfile(
                profile_id="default_high_vol",
                regime=MarketRegime.HIGH_VOLATILITY,
                position_sizing_multiplier=0.4,
                max_leverage=0.5,
                execution_urgency=0.8,
                stop_loss_tightness=1.3,
                max_positions=10,
            ),
        }
        self._profiles = {k.value: v for k, v in defaults.items()}

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("AdaptivePolicy initialized")

    async def shutdown(self) -> None:
        self._profiles.clear()
        self._initialized = False
        logger.info("AdaptivePolicy shutdown complete")

    async def select_profile(self, market_regime: MarketRegime) -> PolicyProfile:
        """Select the optimal policy profile for a market regime.

        Args:
            market_regime: Current market regime.

        Returns:
            Matching PolicyProfile or a default.
        """
        self._active_regime = market_regime
        profile = self._profiles.get(market_regime.value)
        if profile is None:
            profile = self._profiles.get(MarketRegime.RANGING.value)
            if profile is None:
                profile = PolicyProfile(regime=market_regime)
        logger.info("AdaptivePolicy: selected profile for regime=%s", market_regime.value)
        return profile

    async def adapt(self, learning_events: Optional[List[Any]] = None) -> None:
        """Adapt policy based on learning events.

        Args:
            learning_events: Recent learning events to learn from.
        """
        if not learning_events:
            return
        logger.info("AdaptivePolicy: adapting from %d events", len(learning_events))

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "active_regime": self._active_regime.value,
            "profiles": len(self._profiles),
        }
