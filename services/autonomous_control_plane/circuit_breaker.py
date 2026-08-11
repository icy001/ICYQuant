"""
Circuit Breaker — System protection via staged containment.

Stages: Normal → Warning → Restricted → Halted

Triggers on: market data failure, risk engine failure, position
reconciliation failure, execution anomaly, model integrity failure.
"""

from __future__ import annotations

import time
import logging
from enum import Enum
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


class BreakerState(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    RESTRICTED = "restricted"
    HALTED = "halted"


class CircuitBreaker:
    """
    Circuit breaker for autonomous system protection.

    Stages:
        NORMAL → WARNING → RESTRICTED → HALTED

    Trigger conditions:
        - Market data failure
        - Risk engine failure
        - Position reconciliation failure
        - Execution anomaly
        - Model integrity failure
    """

    TRIGGERS = [
        "market_data_failure",
        "risk_engine_failure",
        "position_mismatch",
        "execution_anomaly",
        "model_integrity_failure",
    ]

    def __init__(self, cooldown_seconds: int = 300):
        self._state = BreakerState.NORMAL
        self._cooldown = cooldown_seconds
        self._last_trigger: Optional[float] = None
        self._trigger_history: list[dict] = []
        self._trip_count = 0
        self._on_trip: list[Callable] = []

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def state(self) -> BreakerState:
        return self._state

    @property
    def is_tripped(self) -> bool:
        return self._state in (BreakerState.RESTRICTED, BreakerState.HALTED)

    # ------------------------------------------------------------------
    # Triggers
    # ------------------------------------------------------------------

    def trip(self, trigger: str, reason: str, context: Optional[dict] = None) -> tuple[BreakerState, str]:
        """Trip the circuit breaker."""
        if trigger not in self.TRIGGERS:
            return self._state, f"Unknown trigger: {trigger}"

        # Stage progression
        progression = {
            BreakerState.NORMAL: BreakerState.WARNING,
            BreakerState.WARNING: BreakerState.RESTRICTED,
            BreakerState.RESTRICTED: BreakerState.HALTED,
            BreakerState.HALTED: BreakerState.HALTED,
        }

        old_state = self._state
        self._state = progression.get(self._state, BreakerState.HALTED)
        self._last_trigger = time.time()
        self._trip_count += 1

        self._trigger_history.append({
            "trigger": trigger,
            "reason": reason,
            "from_state": old_state.value,
            "to_state": self._state.value,
            "timestamp": time.time(),
            "context": context,
        })

        logger.critical("CIRCUIT BREAKER: %s → %s (%s: %s)",
                        old_state.value, self._state.value, trigger, reason)

        # Call handlers
        for handler in self._on_trip:
            try:
                handler(self._state, trigger, reason)
            except Exception:
                logger.exception("Circuit breaker handler error")

        return self._state, reason

    def reset(self) -> bool:
        """Reset the circuit breaker to NORMAL."""
        if self._state == BreakerState.HALTED:
            logger.info("Circuit breaker reset: HALTED → NORMAL")
        self._state = BreakerState.NORMAL
        return True

    def on_trip(self, handler: Callable):
        """Register a trip handler."""
        self._on_trip.append(handler)

    # ------------------------------------------------------------------
    # Check
    # ------------------------------------------------------------------

    def can_operate(self) -> tuple[bool, str]:
        """Check if the system can operate normally."""
        if self._state == BreakerState.NORMAL:
            return True, ""
        if self._state == BreakerState.WARNING:
            return True, "Warning — limited operations"
        if self._state == BreakerState.RESTRICTED:
            return False, "Restricted — new operations halted"
        return False, "Halted — all operations stopped"

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        return {
            "state": self._state.value,
            "trip_count": self._trip_count,
            "cooldown_seconds": self._cooldown,
            "recent_triggers": len([t for t in self._trigger_history
                                    if t["timestamp"] > time.time() - 3600]),
        }
