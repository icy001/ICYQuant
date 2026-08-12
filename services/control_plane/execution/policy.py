"""
ExecutionControlPolicy — the configurable knobs of Execution Control
(Commit 26 Part 1.4, spec section 5).

Defaults keep the risk-reduction channels (cancel / reduce / emergency
flatten) open even when the channel is paused, draining or disabled.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionControlPolicy:

    degraded_allow_new: bool = True

    paused_allow_cancel: bool = True

    paused_allow_reduce: bool = True

    draining_allow_cancel: bool = True

    draining_allow_reduce: bool = True

    disabled_allow_cancel: bool = True

    disabled_allow_emergency_flatten: bool = True
