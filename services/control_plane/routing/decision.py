"""
RoutingDecision — the outcome of selecting an execution venue
(Commit 26 Part 1.4, spec section 13).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoutingDecision:

    allowed: bool

    selected_venue: str | None

    fallback_venue: str | None

    reason: str
