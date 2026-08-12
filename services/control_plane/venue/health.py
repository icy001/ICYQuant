"""
Venue health — the observable signal that drives Venue Control
(Commit 26 Part 1.4, spec sections 8, 18–19).

Venue health must NOT directly mutate VenueState.  It flows through:

    Health Monitor → Health Assessment → Control Policy → Venue Controller

This prevents a single transient network glitch from killing a venue.
Later this can be fed by broker/exchange heartbeats, FIX sessions,
WebSocket/REST status, order ACKs, execution reports and cancel ACKs.
"""

from __future__ import annotations

from dataclasses import dataclass

from .state import VenueState


@dataclass(frozen=True)
class VenueHealth:

    venue: str

    healthy: bool

    latency_ms: float

    order_success_rate: float

    cancel_success_rate: float

    reject_rate: float

    heartbeat_ok: bool

    message: str = ""


@dataclass(frozen=True)
class VenueHealthThreshold:

    degraded_latency_ms: float = 500.0

    critical_latency_ms: float = 3000.0

    minimum_order_success_rate: float = 0.95

    minimum_cancel_success_rate: float = 0.98

    maximum_reject_rate: float = 0.10


def assess_venue_state(
    health: VenueHealth,
    threshold: VenueHealthThreshold | None = None,
) -> VenueState:
    """Map raw health telemetry to a VenueState.

    Example mapping (spec section 18):

        latency = 20ms    → ONLINE
        latency = 500ms   → DEGRADED
        latency = 5000ms  → PAUSED
        heartbeat failed  → FAILOVER
    """
    threshold = threshold or VenueHealthThreshold()

    if not health.heartbeat_ok:
        return VenueState.FAILOVER

    if health.latency_ms >= threshold.critical_latency_ms:
        return VenueState.PAUSED

    degraded = False

    if health.latency_ms >= threshold.degraded_latency_ms:
        degraded = True

    if (
        health.order_success_rate
        < threshold.minimum_order_success_rate
    ):
        degraded = True

    if (
        health.cancel_success_rate
        < threshold.minimum_cancel_success_rate
    ):
        degraded = True

    if health.reject_rate > threshold.maximum_reject_rate:
        degraded = True

    return VenueState.DEGRADED if degraded else VenueState.ONLINE
