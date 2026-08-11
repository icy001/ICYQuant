"""
Drawdown Controller — dynamic risk scaling based on portfolio drawdown.

Drawdown Tiers (configurable via Risk Policy):
    Normal:    DD < threshold_1 → Full operation
    Warning:   threshold_1 ≤ DD < threshold_2 → Reduce risk
    Defensive: threshold_2 ≤ DD < threshold_3 → Defensive mode
    Emergency: DD ≥ threshold_3 → Emergency review, minimal exposure
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class DrawdownLevel(Enum):
    """Drawdown severity levels."""
    NORMAL = "normal"
    WARNING = "warning"
    DEFENSIVE = "defensive"
    EMERGENCY = "emergency"


@dataclass
class DrawdownConfig:
    """Drawdown control configuration."""
    warning_threshold: float = 0.05
    defensive_threshold: float = 0.08
    emergency_threshold: float = 0.12
    max_drawdown: float = 0.20
    recovery_factor: float = 0.50  # Only use 50% budget during recovery
    cooling_period_days: int = 5
    max_consecutive_loss_days: int = 5


@dataclass
class DrawdownState:
    """Current drawdown state."""
    peak_value: float = 1.0
    current_value: float = 1.0
    drawdown_pct: float = 0.0
    level: DrawdownLevel = DrawdownLevel.NORMAL
    days_in_drawdown: int = 0
    consecutive_loss_days: int = 0
    max_drawdown_reached: float = 0.0
    recovery_progress: float = 0.0


class DrawdownController:
    """
    Autonomous drawdown management.

    Actions by level:
        NORMAL:
            - Full risk budget
            - Normal position sizing

        WARNING:
            - Reduce risk budget to 70%
            - Reduce new position sizes
            - No new strategies

        DEFENSIVE:
            - Reduce risk budget to 45%
            - Close worst performers
            - Stop new entries

        EMERGENCY:
            - Reduce risk budget to 20%
            - Close most positions
            - Manual review required
            - Kill switch eligible
    """

    def __init__(self, config: Optional[DrawdownConfig] = None) -> None:
        self._config = config or DrawdownConfig()
        self._state = DrawdownState()
        self._history: list[DrawdownState] = []

    def update(self, current_value: float, peak_value: float) -> DrawdownState:
        """Update drawdown state with current portfolio value."""
        self._state.current_value = current_value
        new_peak = max(peak_value, self._state.peak_value)
        self._state.peak_value = new_peak

        dd = (new_peak - current_value) / new_peak if new_peak > 0 else 0
        self._state.drawdown_pct = dd
        self._state.max_drawdown_reached = max(self._state.max_drawdown_reached, dd)

        # Determine level
        if dd >= self._config.emergency_threshold:
            self._state.level = DrawdownLevel.EMERGENCY
        elif dd >= self._config.defensive_threshold:
            self._state.level = DrawdownLevel.DEFENSIVE
        elif dd >= self._config.warning_threshold:
            self._state.level = DrawdownLevel.WARNING
        else:
            self._state.level = DrawdownLevel.NORMAL

        # Recovery progress
        max_dd = self._state.max_drawdown_reached
        if max_dd > 0:
            self._state.recovery_progress = 1.0 - (dd / max_dd) if dd > 0 else 1.0
        else:
            self._state.recovery_progress = 1.0

        # Track days in drawdown
        if dd > 0:
            self._state.days_in_drawdown += 1
        else:
            self._state.days_in_drawdown = 0

        self._history.append(self._state)
        if len(self._history) > 500:
            self._history = self._history[-250:]

        if self._state.level != DrawdownLevel.NORMAL:
            logger.warning(
                "Drawdown: %.2f%% level=%s peak=%.2f recovery=%.0f%%",
                dd * 100, self._state.level.value,
                new_peak, self._state.recovery_progress * 100,
            )

        return self._state

    def get_risk_scale(self) -> float:
        """Get risk scaling factor based on current drawdown level."""
        scales = {
            DrawdownLevel.NORMAL: 1.00,
            DrawdownLevel.WARNING: 0.70,
            DrawdownLevel.DEFENSIVE: 0.45,
            DrawdownLevel.EMERGENCY: 0.20,
        }
        base = scales.get(self._state.level, 1.00)

        # Apply recovery factor during recovery
        if self._state.days_in_drawdown > 0 and self._state.recovery_progress < 0.5:
            base *= self._config.recovery_factor

        return base

    def get_allowed_actions(self) -> dict[str, bool]:
        """Get allowed actions based on current drawdown level."""
        if self._state.level == DrawdownLevel.NORMAL:
            return {"new_entries": True, "increase_positions": True,
                    "new_strategies": True, "auto_execute": True}
        elif self._state.level == DrawdownLevel.WARNING:
            return {"new_entries": True, "increase_positions": False,
                    "new_strategies": False, "auto_execute": True}
        elif self._state.level == DrawdownLevel.DEFENSIVE:
            return {"new_entries": False, "increase_positions": False,
                    "new_strategies": False, "auto_execute": False}
        else:  # EMERGENCY
            return {"new_entries": False, "increase_positions": False,
                    "new_strategies": False, "auto_execute": False}

    @property
    def state(self) -> DrawdownState:
        return self._state

    @property
    def is_normal(self) -> bool:
        return self._state.level == DrawdownLevel.NORMAL

    @property
    def is_emergency(self) -> bool:
        return self._state.level == DrawdownLevel.EMERGENCY

    def get_history(self, limit: int = 30) -> list[DrawdownState]:
        return self._history[-limit:]
