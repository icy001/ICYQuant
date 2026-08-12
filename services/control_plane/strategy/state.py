"""
StrategyState — the state model of a strategy under Institutional Control
(Commit 26 Part 1.3, spec section 3).

Real trading systems cannot simply jump RUNNING → DISABLED.  A misbehaving
strategy often needs a controlled risk-reduction path:

    RUNNING
        ↓
    DRAINING
        ↓
    stop producing new risk
        ↓
    wait for the position to decay
        ↓
    DISABLED

``RECOVERING`` is the explicit transition state used while the strategy is
being brought back under control after an incident — it is fail-closed by
default (no trading capability) until an authorized operator returns the
strategy to RUNNING.
"""

from __future__ import annotations

from enum import Enum


class StrategyState(str, Enum):

    RUNNING = "RUNNING"

    PAUSED = "PAUSED"

    DISABLED = "DISABLED"

    DRAINING = "DRAINING"

    RECOVERING = "RECOVERING"

    @property
    def trading_capability(self) -> str:
        """Human-readable trading capability summary of this state."""
        if self is StrategyState.RUNNING:
            return "signal+new+reduce"
        if self in {
            StrategyState.PAUSED,
            StrategyState.DRAINING,
            StrategyState.DISABLED,
            StrategyState.RECOVERING,
        }:
            return "reduce-only-or-blocked"
        return "unknown"
