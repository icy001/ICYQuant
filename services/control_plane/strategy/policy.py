"""
StrategyControlPolicy — the configurable knobs of Strategy Control
(Commit 26 Part 1.3, spec section 5).

Defaults encode the fail-safe principle: every non-RUNNING state blocks signal
generation and new orders, but keeps the position-reduction channel open so the
strategy can always wind down its existing risk:

    RUNNING    Signal ✅  New Order ✅  Reduce ✅
    PAUSED     Signal ❌  New Order ❌  Reduce ✅
    DRAINING   Signal ❌  New Order ❌  Reduce ✅
    DISABLED   Signal ❌  New Order ❌  Reduce ✅
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyControlPolicy:

    paused_allow_reduce: bool = True

    draining_allow_reduce: bool = True

    disabled_allow_reduce: bool = True

    disabled_allow_signal: bool = False
