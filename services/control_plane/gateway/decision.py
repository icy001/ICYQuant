"""
GatewayDecision — the three-valued outcome of the Institutional Control
Gateway.

Two values (ALLOW / BLOCK) are not enough for a quantitative trading system.
When a strategy misbehaves we often want to forbid new positions (BUY,
SELL OPEN) while still permitting position reduction (SELL CLOSE, BUY CLOSE):

    ALLOW        → the request may proceed normally
    REDUCE_ONLY  → only position-reducing orders are allowed
    BLOCK        → the request is fully forbidden

(spec section 13)
"""

from __future__ import annotations

from enum import Enum


class ControlDecision(str, Enum):
    ALLOW = "ALLOW"

    REDUCE_ONLY = "REDUCE_ONLY"

    BLOCK = "BLOCK"

    @property
    def is_blocking(self) -> bool:
        return self is ControlDecision.BLOCK

    @property
    def permits(self) -> bool:
        return self is ControlDecision.ALLOW or self is ControlDecision.REDUCE_ONLY


class ControlDecisionReason(str, Enum):
    NO_ACTIVE_CONTROL = "NO_ACTIVE_CONTROL"

    GLOBAL_KILL_SWITCH = "GLOBAL_KILL_SWITCH"

    ACCOUNT_BLOCKED = "ACCOUNT_BLOCKED"

    STRATEGY_DISABLED = "STRATEGY_DISABLED"

    SYMBOL_BLOCKED = "SYMBOL_BLOCKED"

    VENUE_DISABLED = "VENUE_DISABLED"

    REDUCE_ONLY_MODE = "REDUCE_ONLY_MODE"

    EXECUTION_DISABLED = "EXECUTION_DISABLED"
