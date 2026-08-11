"""
Kill Switch — highest-level emergency stop for autonomous execution.

Trigger conditions:
    - Risk breach (VaR/ES/drawdown limits exceeded)
    - Execution anomaly (excessive slippage, fills, cost)
    - Market data failure (data gap, stale prices)
    - Model failure (prediction quality degradation)
    - Broker failure (connection loss, rejections)
    - Position mismatch (book vs expected)
    - Extreme volatility
    - System integrity failure
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class KillSwitchTrigger(Enum):
    """Kill switch trigger types."""
    RISK_BREACH = "risk_breach"
    EXECUTION_ANOMALY = "execution_anomaly"
    MARKET_DATA_FAILURE = "market_data_failure"
    MODEL_FAILURE = "model_failure"
    BROKER_FAILURE = "broker_failure"
    POSITION_MISMATCH = "position_mismatch"
    EXTREME_VOLATILITY = "extreme_volatility"
    SYSTEM_INTEGRITY = "system_integrity"
    MANUAL = "manual"


class KillSwitchLevel(Enum):
    """Kill switch severity levels."""
    WARNING = "warning"  # Alert only
    RESTRICTED = "restricted"  # No new orders
    SOFT_KILL = "soft_kill"  # Cancel open orders, no new
    HARD_KILL = "hard_kill"  # Cancel all, halt autonomous execution


@dataclass
class KillSwitchEvent:
    """A kill switch trigger event."""
    id: str = field(default_factory=lambda: str(uuid4()))
    trigger: KillSwitchTrigger
    level: KillSwitchLevel = KillSwitchLevel.SOFT_KILL
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    triggered_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    auto_resolve: bool = False


@dataclass
class KillSwitchState:
    """Current kill switch state."""
    is_active: bool = False
    level: KillSwitchLevel = KillSwitchLevel.WARNING
    active_events: list[KillSwitchEvent] = field(default_factory=list)
    total_triggers: int = 0
    last_trigger: Optional[datetime] = None


class KillSwitch:
    """
    Autonomous execution kill switch.

    Actions by level:
        WARNING: Alert only, no action
        RESTRICTED: Stop new orders, allow existing to complete
        SOFT_KILL: Cancel all open orders, no new orders
        HARD_KILL: Cancel all orders, halt all autonomous execution,
                  notify Risk/Approval, require manual reset
    """

    def __init__(self) -> None:
        self._state = KillSwitchState()
        self._event_history: list[KillSwitchEvent] = []

    # ── Trigger Conditions ─────────────────────────────────────

    def check_risk_breach(
        self, var: float, var_limit: float, drawdown: float, dd_limit: float,
    ) -> Optional[KillSwitchEvent]:
        """Check for risk limit breach."""
        if var > var_limit * 1.5:
            return self.trigger(
                KillSwitchTrigger.RISK_BREACH,
                KillSwitchLevel.SOFT_KILL,
                f"VaR {var:.2%} exceeds 150% of limit {var_limit:.2%}",
            )
        if drawdown > dd_limit:
            return self.trigger(
                KillSwitchTrigger.RISK_BREACH,
                KillSwitchLevel.RESTRICTED,
                f"Drawdown {drawdown:.2%} exceeds limit {dd_limit:.2%}",
            )
        return None

    def check_execution_anomaly(
        self, consecutive_slippage_violations: int,
    ) -> Optional[KillSwitchEvent]:
        """Check for execution anomalies."""
        if consecutive_slippage_violations >= 10:
            return self.trigger(
                KillSwitchTrigger.EXECUTION_ANOMALY,
                KillSwitchLevel.SOFT_KILL,
                f"{consecutive_slippage_violations} consecutive slippage violations",
            )
        return None

    def check_market_data_failure(
        self, data_age_seconds: float, max_age: float = 120,
    ) -> Optional[KillSwitchEvent]:
        """Check for market data staleness."""
        if data_age_seconds > max_age:
            return self.trigger(
                KillSwitchTrigger.MARKET_DATA_FAILURE,
                KillSwitchLevel.RESTRICTED,
                f"Market data stale for {data_age_seconds:.0f}s (max {max_age}s)",
            )
        return None

    def check_extreme_volatility(
        self, current_vol: float, normal_vol: float,
    ) -> Optional[KillSwitchEvent]:
        """Check for extreme volatility."""
        if normal_vol > 0 and current_vol / normal_vol > 5:
            return self.trigger(
                KillSwitchTrigger.EXTREME_VOLATILITY,
                KillSwitchLevel.RESTRICTED,
                f"Volatility {current_vol:.2%} is {current_vol/normal_vol:.1f}x normal",
            )
        return None

    # ── Trigger / Resolve ──────────────────────────────────────

    def trigger(
        self,
        trigger: KillSwitchTrigger,
        level: KillSwitchLevel = KillSwitchLevel.SOFT_KILL,
        reason: str = "",
        details: Optional[dict] = None,
    ) -> KillSwitchEvent:
        """Trigger a kill switch event."""
        event = KillSwitchEvent(
            trigger=trigger, level=level, reason=reason,
            details=details or {},
        )
        self._event_history.append(event)
        self._state.active_events.append(event)
        self._state.total_triggers += 1
        self._state.last_trigger = datetime.now()

        # Escalate level
        severity_order = {
            KillSwitchLevel.WARNING: 0,
            KillSwitchLevel.RESTRICTED: 1,
            KillSwitchLevel.SOFT_KILL: 2,
            KillSwitchLevel.HARD_KILL: 3,
        }
        if severity_order[level] > severity_order[self._state.level]:
            self._state.level = level

        self._state.is_active = True

        logger.critical(
            "KILL SWITCH TRIGGERED: %s level=%s reason=%s",
            trigger.value, level.value, reason,
        )
        return event

    def resolve(self, event_id: str) -> Optional[KillSwitchEvent]:
        """Resolve a kill switch event."""
        for event in self._state.active_events:
            if event.id == event_id:
                event.resolved_at = datetime.now()
                self._state.active_events.remove(event)

                if not self._state.active_events:
                    self._state.is_active = False
                    self._state.level = KillSwitchLevel.WARNING
                    logger.info("All kill switch events resolved")

                return event
        return None

    def manual_override(self) -> None:
        """Manual override — resolve all events."""
        self._state = KillSwitchState()
        logger.warning("Kill switch manually overridden")

    # ── Actions ────────────────────────────────────────────────

    def should_allow_new_orders(self) -> bool:
        """Check if new orders are allowed."""
        if not self._state.is_active:
            return True
        return self._state.level == KillSwitchLevel.WARNING

    def should_cancel_open_orders(self) -> bool:
        """Check if open orders should be cancelled."""
        if not self._state.is_active:
            return False
        return self._state.level in (
            KillSwitchLevel.SOFT_KILL, KillSwitchLevel.HARD_KILL,
        )

    def should_halt_autonomy(self) -> bool:
        """Check if autonomous execution should be halted."""
        if not self._state.is_active:
            return False
        return self._state.level == KillSwitchLevel.HARD_KILL

    @property
    def state(self) -> KillSwitchState:
        return self._state

    @property
    def is_active(self) -> bool:
        return self._state.is_active

    @property
    def event_history(self) -> list[KillSwitchEvent]:
        return self._event_history[-50:]
