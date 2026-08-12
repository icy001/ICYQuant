"""
TradingState — whether the system is currently allowed to trade, and at what
level.

Trading State is deliberately separated from System State: a system can be
DEGRADED (non-critical component down) while trading stays TRADING_READY, and
conversely a manual halt can freeze trading while the system itself remains
READY for monitoring / recovery / reporting.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Set


class TradingState(str, Enum):
    """Current trading permission level."""

    TRADING_DISABLED = "TRADING_DISABLED"
    """Trading is not enabled yet (startup phase)."""

    TRADING_READY = "TRADING_READY"
    """Trading is fully allowed."""

    TRADING_DEGRADED = "TRADING_DEGRADED"
    """Trading is allowed but constrained (core inputs degraded)."""

    TRADING_HALTED = "TRADING_HALTED"
    """Trading is blocked — new orders are rejected."""

    @property
    def is_ready(self) -> bool:
        return self is TradingState.TRADING_READY

    @property
    def is_halted(self) -> bool:
        return self is TradingState.TRADING_HALTED

    @property
    def is_disabled(self) -> bool:
        return self is TradingState.TRADING_DISABLED


class TradingStateTransitionError(Exception):
    """Raised when a trading state transition is rejected."""

    def __init__(self, from_state: TradingState, to_state: TradingState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid trading state transition: {from_state.value} -> {to_state.value}")


class TradingStateMachine:
    """Allowed trading state transitions."""

    ALLOWED_TRANSITIONS: Dict[TradingState, Set[TradingState]] = {
        TradingState.TRADING_DISABLED: {TradingState.TRADING_READY},
        TradingState.TRADING_READY: {
            TradingState.TRADING_DEGRADED,
            TradingState.TRADING_HALTED,
        },
        TradingState.TRADING_DEGRADED: {
            TradingState.TRADING_READY,
            TradingState.TRADING_HALTED,
        },
        TradingState.TRADING_HALTED: {
            TradingState.TRADING_READY,
            TradingState.TRADING_DEGRADED,
        },
    }

    @classmethod
    def can_transition(cls, from_state: TradingState, to_state: TradingState) -> bool:
        return to_state in cls.ALLOWED_TRANSITIONS.get(from_state, set())

    @classmethod
    def assert_transition(cls, from_state: TradingState, to_state: TradingState) -> None:
        if not cls.can_transition(from_state, to_state):
            raise TradingStateTransitionError(from_state, to_state)
