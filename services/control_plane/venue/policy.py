"""
VenueControlPolicy — the configurable knobs of Venue Control
(Commit 26 Part 1.4, spec section 10).

Defaults: a DEGRADED venue stops new orders but keeps the risk-reduction
capability (cancel / reduce / emergency flatten) open.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VenueControlPolicy:

    degraded_allow_new: bool = False

    paused_allow_new: bool = False

    paused_allow_cancel: bool = True

    paused_allow_reduce: bool = True

    disabled_allow_cancel: bool = True

    disabled_allow_reduce: bool = False

    disabled_allow_emergency_flatten: bool = True
