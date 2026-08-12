"""Tests for VenueHealth / VenueHealthThreshold / assess_venue_state
(Commit 26 Part 1.4, spec sections 8, 18–19)."""

from services.control_plane.venue import (
    VenueHealth,
    VenueHealthThreshold,
    VenueState,
    assess_venue_state,
)


def _health(
    *,
    venue="NASDAQ",
    healthy=True,
    latency_ms=20.0,
    order_success_rate=0.99,
    cancel_success_rate=0.99,
    reject_rate=0.01,
    heartbeat_ok=True,
    message="",
) -> VenueHealth:
    return VenueHealth(
        venue=venue,
        healthy=healthy,
        latency_ms=latency_ms,
        order_success_rate=order_success_rate,
        cancel_success_rate=cancel_success_rate,
        reject_rate=reject_rate,
        heartbeat_ok=heartbeat_ok,
        message=message,
    )


def test_low_latency_is_online():
    assert (
        assess_venue_state(_health(latency_ms=20.0))
        is VenueState.ONLINE
    )


def test_degraded_latency_is_degraded():
    assert (
        assess_venue_state(_health(latency_ms=500.0))
        is VenueState.DEGRADED
    )


def test_critical_latency_is_paused():
    assert (
        assess_venue_state(_health(latency_ms=5000.0))
        is VenueState.PAUSED
    )


def test_heartbeat_loss_is_failover():
    assert (
        assess_venue_state(_health(heartbeat_ok=False))
        is VenueState.FAILOVER
    )


def test_low_order_success_rate_is_degraded():
    assert (
        assess_venue_state(_health(order_success_rate=0.80))
        is VenueState.DEGRADED
    )


def test_high_reject_rate_is_degraded():
    assert (
        assess_venue_state(_health(reject_rate=0.35))
        is VenueState.DEGRADED
    )


def test_low_cancel_success_rate_is_degraded():
    assert (
        assess_venue_state(_health(cancel_success_rate=0.90))
        is VenueState.DEGRADED
    )


def test_health_threshold_defaults():
    threshold = VenueHealthThreshold()
    assert threshold.degraded_latency_ms == 500.0
    assert threshold.critical_latency_ms == 3000.0
    assert threshold.minimum_order_success_rate == 0.95
    assert threshold.minimum_cancel_success_rate == 0.98
    assert threshold.maximum_reject_rate == 0.10


def test_custom_threshold_is_respected():
    threshold = VenueHealthThreshold(
        degraded_latency_ms=100.0,
        critical_latency_ms=200.0,
    )
    assert (
        assess_venue_state(
            _health(latency_ms=150.0),
            threshold,
        )
        is VenueState.DEGRADED
    )
    assert (
        assess_venue_state(
            _health(latency_ms=250.0),
            threshold,
        )
        is VenueState.PAUSED
    )


def test_health_is_frozen():
    import pytest

    with pytest.raises(Exception):
        _health().latency_ms = 999.0  # type: ignore[misc]


def test_threshold_is_frozen():
    import pytest

    with pytest.raises(Exception):
        VenueHealthThreshold().critical_latency_ms = 1.0  # type: ignore[misc]
