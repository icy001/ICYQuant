"""
Regime Risk Controller — market regime-aware risk adjustments.

Connects market regime detection from Part 1.3 to the risk system:

    TRENDING → Normal risk, momentum-friendly
    HIGH_VOL → Reduced risk, wider stops
    RISK_OFF → Defensive risk, liquidity focus
    CRISIS → Emergency risk, minimal exposure
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class RegimeRiskProfile:
    """Risk profile for a specific market regime."""
    regime: str = "NORMAL"
    risk_budget_scale: float = 1.00
    max_position_size: float = 0.20
    max_leverage: float = 3.0
    max_gross_exposure: float = 2.0
    stop_loss_multiplier: float = 1.00
    take_profit_multiplier: float = 1.00
    max_new_entries: int = 10
    require_confirmation: bool = False
    prefer_liquid: bool = False
    description: str = ""


class RegimeRiskController:
    """
    Regime-aware risk control.

    Predefined regime profiles:
        NORMAL:        Standard risk parameters
        TRENDING:      Slightly aggressive, momentum-friendly
        MEAN_REVERTING: Wider stops, patience required
        HIGH_VOL:      Reduced exposure, tighter stops
        RISK_OFF:      Defensive allocation, high liquidity preference
        CRISIS:        Emergency mode, minimal exposure, no new entries
    """

    REGIME_PROFILES: dict[str, RegimeRiskProfile] = {
        "NORMAL": RegimeRiskProfile(
            regime="NORMAL", risk_budget_scale=1.00,
            max_position_size=0.20, max_leverage=3.0,
            max_gross_exposure=2.0, stop_loss_multiplier=1.00,
            take_profit_multiplier=1.00, max_new_entries=10,
            description="Standard risk parameters",
        ),
        "TRENDING": RegimeRiskProfile(
            regime="TRENDING", risk_budget_scale=0.90,
            max_position_size=0.22, max_leverage=3.0,
            max_gross_exposure=2.0, stop_loss_multiplier=0.85,
            take_profit_multiplier=1.15, max_new_entries=10,
            description="Momentum-friendly, tighter stops",
        ),
        "MEAN_REVERTING": RegimeRiskProfile(
            regime="MEAN_REVERTING", risk_budget_scale=0.75,
            max_position_size=0.15, max_leverage=2.0,
            max_gross_exposure=1.5, stop_loss_multiplier=1.30,
            take_profit_multiplier=0.80, max_new_entries=5,
            description="Wider stops, quicker takes",
        ),
        "HIGH_VOL": RegimeRiskProfile(
            regime="HIGH_VOL", risk_budget_scale=0.60,
            max_position_size=0.12, max_leverage=2.0,
            max_gross_exposure=1.5, stop_loss_multiplier=1.50,
            take_profit_multiplier=0.70, max_new_entries=3,
            prefer_liquid=True,
            description="Reduced exposure, wider stops",
        ),
        "RISK_OFF": RegimeRiskProfile(
            regime="RISK_OFF", risk_budget_scale=0.35,
            max_position_size=0.08, max_leverage=1.5,
            max_gross_exposure=1.0, stop_loss_multiplier=2.00,
            take_profit_multiplier=0.50, max_new_entries=1,
            require_confirmation=True, prefer_liquid=True,
            description="Defensive, high liquidity focus",
        ),
        "CRISIS": RegimeRiskProfile(
            regime="CRISIS", risk_budget_scale=0.15,
            max_position_size=0.05, max_leverage=1.0,
            max_gross_exposure=0.5, stop_loss_multiplier=3.00,
            take_profit_multiplier=0.30, max_new_entries=0,
            require_confirmation=True, prefer_liquid=True,
            description="Emergency mode, minimal exposure",
        ),
    }

    def __init__(self) -> None:
        self._current_regime = "NORMAL"
        self._regime_history: list[tuple[datetime, str]] = []

    def set_regime(self, regime: str) -> RegimeRiskProfile:
        """Set the current market regime."""
        self._current_regime = regime
        self._regime_history.append((datetime.now(), regime))
        if len(self._regime_history) > 1000:
            self._regime_history = self._regime_history[-500:]

        profile = self.get_profile(regime)
        logger.info(
            "Regime set: %s → budget=%.0f%% max_pos=%.0f%%",
            regime, profile.risk_budget_scale * 100,
            profile.max_position_size * 100,
        )
        return profile

    def get_profile(self, regime: Optional[str] = None) -> RegimeRiskProfile:
        """Get risk profile for a regime."""
        r = regime or self._current_regime
        return self.REGIME_PROFILES.get(r, self.REGIME_PROFILES["NORMAL"])

    def get_risk_budget_scale(self) -> float:
        """Get current regime's risk budget scaling."""
        return self.get_profile().risk_budget_scale

    def get_max_position_size(self) -> float:
        """Get current regime's max position size."""
        return self.get_profile().max_position_size

    def get_max_leverage(self) -> float:
        """Get current regime's max leverage."""
        return self.get_profile().max_leverage

    def should_allow_new_entries(self) -> bool:
        """Check if new entries are allowed in current regime."""
        return self.get_profile().max_new_entries > 0

    def requires_confirmation(self) -> bool:
        """Check if manual confirmation is required."""
        return self.get_profile().require_confirmation

    def prefers_liquid(self) -> bool:
        """Check if liquid assets are preferred."""
        return self.get_profile().prefer_liquid

    def get_stop_multiplier(self) -> float:
        """Get stop loss multiplier for current regime."""
        return self.get_profile().stop_loss_multiplier

    @property
    def current_regime(self) -> str:
        return self._current_regime

    def get_regime_history(self, limit: int = 20) -> list[tuple[datetime, str]]:
        return self._regime_history[-limit:]
