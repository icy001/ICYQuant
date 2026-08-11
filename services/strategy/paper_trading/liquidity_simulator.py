"""
Liquidity Simulator
===================
Simulates market liquidity constraints and partial fills.

Pipeline:
    Market Volume → Available Liquidity → Partial Fill → Remaining Order

Supports partial fills based on available market depth.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class LiquidityProfile:
    """Liquidity profile for an instrument."""
    instrument: str = ""
    avg_daily_volume: float = 0.0        # Average daily volume
    max_participation_rate: float = 0.10  # Max % of ADV per trade
    bid_ask_spread_bps: float = 5.0
    depth_at_best: float = 0.0            # Shares at best bid/ask


@dataclass
class LiquidityResult:
    """Liquidity simulation result."""
    requested_quantity: float = 0.0
    fillable_quantity: float = 0.0
    fill_rate: float = 0.0         # fillable / requested
    is_partial: bool = False
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LiquiditySimulator:
    """Simulates market liquidity constraints.

    Limits trade sizes based on participation rate and available depth.
    """

    def __init__(self, model: str = "full"):
        self._model = model              # full / partial / realistic
        self._profiles: Dict[str, LiquidityProfile] = {}
        self._default_participation_rate = 0.10
        self.is_initialized = False

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("LiquiditySimulator initialized (model=%s)", self._model)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_model(self, model: str) -> None:
        self._model = model

    def register_profile(self, profile: LiquidityProfile) -> None:
        self._profiles[profile.instrument] = profile

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    async def simulate(self, instrument: str,
                       quantity: float) -> LiquidityResult:
        """Simulate available liquidity for a trade."""
        if self._model == "full":
            return LiquidityResult(
                requested_quantity=quantity,
                fillable_quantity=quantity,
                fill_rate=1.0,
                is_partial=False,
                reason="full_liquidity_model",
            )

        profile = self._profiles.get(instrument)
        if not profile:
            # Default: assume unlimited but with participation rate
            max_qty = max(quantity * 10, 10000)  # Arbitrary depth
            fillable = min(quantity, max_qty * self._default_participation_rate)
            return LiquidityResult(
                requested_quantity=quantity,
                fillable_quantity=fillable,
                fill_rate=fillable / quantity if quantity > 0 else 0,
                is_partial=fillable < quantity,
                reason="default_liquidity",
            )

        # Profile-based
        max_participation = profile.avg_daily_volume * profile.max_participation_rate
        fillable = min(quantity, max_participation, profile.depth_at_best or quantity)

        if self._model == "realistic":
            # Add random variance
            variance = random.uniform(0.8, 1.0)
            fillable *= variance

        return LiquidityResult(
            requested_quantity=quantity,
            fillable_quantity=min(fillable, quantity),
            fill_rate=min(fillable, quantity) / quantity if quantity > 0 else 0,
            is_partial=fillable < quantity,
            reason=f"profile_based (ADV={profile.avg_daily_volume})",
        )

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "model": self._model,
            "profiles_registered": len(self._profiles),
            "default_participation_rate": self._default_participation_rate,
        }
