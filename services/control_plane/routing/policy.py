"""
RoutingPolicy — the configurable knobs of Routing Control
(Commit 26 Part 1.4, spec section 14).

This layer only establishes the *control* surface — the full smart-routing
logic (instrument support, trading session, account permission, currency,
position, risk limits, order type, liquidity, price, venue mapping) is left
to the Execution Routing Layer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoutingPolicy:

    enable_failover: bool = True

    allow_cross_venue_routing: bool = True

    require_healthy_venue: bool = True
