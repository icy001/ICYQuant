"""Unit tests: ComponentMonitor — events, hysteresis, incidents, recovery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.control_plane.domain.component_registry import ComponentCriticality
from services.control_plane.events.component_unresponsive import ComponentUnresponsive
from services.control_plane.events.health_status_changed import HealthStatusChanged
from services.control_plane.events.heartbeat_missed import HeartbeatMissed
from services.control_plane.health.health_evaluator import HealthEvaluator
from services.control_plane.health.health_incident import (
    HealthIncidentState,
    HealthIncidentTransitionError,
)
from services.control_plane.health.health_profile import HealthProfile
from services.control_plane.health.health_status import HealthStatus
from services.control_plane.health.heartbeat import Heartbeat
from services.control_plane.health.readiness import (
    DependencyStatus,
    FreshnessPolicy,
)
from services.control_plane.monitors.component_monitor import ComponentMonitor
from services.control_plane.monitors.heartbeat_monitor import HeartbeatMonitor

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


def hb(
    component_id="risk_engine",
    instance_id="risk-01",
    sequence=100,
    timestamp=NOW,
):
    return Heartbeat(
        component_id=component_id,
        instance_id=instance_id,
        sequence=sequence,
        timestamp=timestamp,
    )


def risk_profile(**kwargs):
    defaults = dict(
        component_id="risk_engine",
        criticality=ComponentCriticality.TRADING_CRITICAL,
        heartbeat_interval=5.0,
        warning_timeout=10.0,
        critical_timeout=15.0,
        startup_grace_period=30.0,
    )
    defaults.update(kwargs)
    return HealthProfile(**defaults)


def make_monitor(profiles=None, on_event=None, **kwargs):
    monitor = ComponentMonitor(
        heartbeat_monitor=HeartbeatMonitor(
            warning_timeout=10.0,
            critical_timeout=15.0,
            startup_grace_period=30.0,
            failure_threshold=3,
        ),
        health_evaluator=HealthEvaluator(),
        failure_threshold=3,
        recovery_confirmation_count=3,
        on_event=on_event,
    )
    for profile in profiles or [risk_profile()]:
        monitor.register_profile(profile)
    return monitor


class TestHeartbeatIdempotency:
    def test_duplicate_sequence_rejected(self):
        monitor = make_monitor()
        assert monitor.record_heartbeat(hb(sequence=100)) is True
        assert monitor.record_heartbeat(hb(sequence=100)) is False
        assert monitor.last_heartbeat("risk_engine").sequence == 100

    def test_out_of_order_sequence_rejected(self):
        monitor = make_monitor()
        assert monitor.record_heartbeat(hb(sequence=102)) is True
        assert monitor.record_heartbeat(hb(sequence=101)) is False
        assert monitor.last_heartbeat("risk_engine").sequence == 102

    def test_new_sequence_accepted(self):
        monitor = make_monitor()
        assert monitor.record_heartbeat(hb(sequence=100)) is True
        assert monitor.record_heartbeat(hb(sequence=101)) is True
        assert monitor.last_heartbeat("risk_engine").sequence == 101


class TestInstanceIdentity:
    def test_instances_are_distinct(self):
        monitor = make_monitor()
        monitor.record_heartbeat(
            hb(component_id="position", instance_id="position-01", sequence=100)
        )
        monitor.record_heartbeat(
            hb(component_id="position", instance_id="position-02", sequence=105)
        )
        last = monitor.last_heartbeat("position")
        assert last.instance_id == "position-02"
        assert last.sequence == 105

    def test_same_sequence_across_instances_both_accepted(self):
        monitor = make_monitor()
        assert (
            monitor.record_heartbeat(
                hb(component_id="position", instance_id="position-01", sequence=100)
            )
            is True
        )
        assert (
            monitor.record_heartbeat(
                hb(component_id="position", instance_id="position-02", sequence=100)
            )
            is True
        )


class TestHealthyComponent:
    def test_fresh_heartbeat_is_healthy(self):
        monitor = make_monitor()
        monitor.record_heartbeat(hb(timestamp=NOW - timedelta(seconds=2)))
        evaluation = monitor.evaluate("risk_engine", now=NOW)
        assert evaluation.status is HealthStatus.HEALTHY
        assert monitor.health_status("risk_engine") is HealthStatus.HEALTHY

    def test_initial_change_event_emitted(self):
        monitor = make_monitor()
        monitor.record_heartbeat(hb(timestamp=NOW - timedelta(seconds=2)))
        monitor.evaluate("risk_engine", now=NOW)
        changed = [e for e in monitor.events if isinstance(e, HealthStatusChanged)]
        assert len(changed) == 1
        assert changed[0].previous_status is HealthStatus.UNKNOWN
        assert changed[0].current_status is HealthStatus.HEALTHY


class TestHeartbeatMissedEvent:
    def test_missed_event_emitted(self):
        monitor = make_monitor()
        monitor.record_heartbeat(hb(timestamp=NOW - timedelta(seconds=20)))
        monitor.evaluate("risk_engine", now=NOW)
        missed = [e for e in monitor.events if isinstance(e, HeartbeatMissed)]
        assert len(missed) == 1
        assert missed[0].component_id == "risk_engine"
        assert missed[0].miss_count == 1
        assert missed[0].last_sequence == 100


class TestFailureHysteresis:
    def test_unhealthy_only_after_threshold_misses(self):
        monitor = make_monitor()
        monitor.record_heartbeat(hb(timestamp=NOW - timedelta(seconds=20)))
        monitor.evaluate("risk_engine", now=NOW)
        assert monitor.miss_count("risk_engine") == 1

        monitor.evaluate("risk_engine", now=NOW)
        assert monitor.miss_count("risk_engine") == 2

        monitor.evaluate("risk_engine", now=NOW)
        assert monitor.miss_count("risk_engine") == 3
        assert monitor.health_status("risk_engine") is HealthStatus.UNHEALTHY

    def test_unresponsive_event_after_threshold(self):
        monitor = make_monitor()
        monitor.record_heartbeat(hb(timestamp=NOW - timedelta(seconds=20)))
        for _ in range(3):
            monitor.evaluate("risk_engine", now=NOW)
        unresponsive = [
            e for e in monitor.events if isinstance(e, ComponentUnresponsive)
        ]
        assert len(unresponsive) == 1
        assert unresponsive[0].component_id == "risk_engine"
        assert unresponsive[0].current_health is HealthStatus.UNHEALTHY

    def test_single_heartbeat_miss_is_degraded_not_unhealthy(self):
        # Warning window (elapsed <= critical) after one miss → DEGRADED.
        monitor = make_monitor()
        monitor.record_heartbeat(hb(timestamp=NOW - timedelta(seconds=12)))
        monitor.evaluate("risk_engine", now=NOW)
        assert monitor.health_status("risk_engine") is HealthStatus.DEGRADED


class TestRecoveryHysteresis:
    def test_needs_three_confirmed_healthy_checks(self):
        monitor = make_monitor()
        # 1) Enter DEGRADED via warning timeout.
        monitor.record_heartbeat(hb(timestamp=NOW - timedelta(seconds=12)))
        monitor.evaluate("risk_engine", now=NOW)
        assert monitor.health_status("risk_engine") is HealthStatus.DEGRADED
        monitor.evaluate("risk_engine", now=NOW)

        # 2) Heartbeat resumes — recovery needs 3 confirmations.
        monitor.record_heartbeat(hb(sequence=101, timestamp=NOW))
        monitor.evaluate("risk_engine", now=NOW + timedelta(seconds=1))
        assert monitor.health_status("risk_engine") is HealthStatus.DEGRADED
        assert monitor.success_count("risk_engine") == 1

        monitor.evaluate("risk_engine", now=NOW + timedelta(seconds=2))
        assert monitor.health_status("risk_engine") is HealthStatus.DEGRADED
        assert monitor.success_count("risk_engine") == 2

        monitor.evaluate("risk_engine", now=NOW + timedelta(seconds=3))
        assert monitor.health_status("risk_engine") is HealthStatus.HEALTHY
        assert monitor.success_count("risk_engine") == 3


class TestHealthRecovery:
    def test_unhealthy_to_healthy_cycle(self):
        monitor = make_monitor()
        # Two critical misses → UNHEALTHY.
        monitor.record_heartbeat(hb(timestamp=NOW - timedelta(seconds=20)))
        monitor.evaluate("risk_engine", now=NOW)
        monitor.evaluate("risk_engine", now=NOW)
        assert monitor.health_status("risk_engine") is HealthStatus.UNHEALTHY

        # Heartbeat resumes → full recovery cycle.
        monitor.record_heartbeat(hb(sequence=101, timestamp=NOW))
        for offset in range(1, 4):
            monitor.evaluate("risk_engine", now=NOW + timedelta(seconds=offset))
        assert monitor.health_status("risk_engine") is HealthStatus.HEALTHY

        # Recovery emitted a HEALTH_STATUS_CHANGED to HEALTHY.
        changed = [
            e
            for e in monitor.events
            if isinstance(e, HealthStatusChanged)
            and e.current_status is HealthStatus.HEALTHY
        ]
        assert changed
        # Component recovery does NOT re-open trading by itself — it just
        # changes health; the Control Plane decides on trading.
        assert monitor.miss_count("risk_engine") == 0


class TestHealthIncidentLifecycle:
    def test_incident_open_on_degraded(self):
        monitor = make_monitor()
        monitor.record_heartbeat(hb(timestamp=NOW - timedelta(seconds=12)))
        monitor.evaluate("risk_engine", now=NOW)
        incident = monitor.incident("risk_engine")
        assert incident is not None
        assert incident.state is HealthIncidentState.OPEN
        assert incident.severity == "CRITICAL"  # TRADING_CRITICAL component

    def test_incident_recovering_then_resolved(self):
        monitor = make_monitor()
        monitor.record_heartbeat(hb(timestamp=NOW - timedelta(seconds=12)))
        monitor.evaluate("risk_engine", now=NOW)
        monitor.evaluate("risk_engine", now=NOW)
        assert monitor.incident("risk_engine").state is HealthIncidentState.OPEN

        monitor.record_heartbeat(hb(sequence=101, timestamp=NOW))
        monitor.evaluate("risk_engine", now=NOW + timedelta(seconds=1))
        assert (
            monitor.incident("risk_engine").state is HealthIncidentState.RECOVERING
        )

        for offset in range(2, 4):
            monitor.evaluate("risk_engine", now=NOW + timedelta(seconds=offset))
        incident = monitor.incident("risk_engine")
        assert incident.state is HealthIncidentState.RESOLVED
        assert incident.resolved_at is not None

    def test_incident_escalated_when_unresponsive(self):
        monitor = make_monitor()
        monitor.record_heartbeat(hb(timestamp=NOW - timedelta(seconds=20)))
        for _ in range(3):
            monitor.evaluate("risk_engine", now=NOW)
        assert monitor.incident("risk_engine").state is HealthIncidentState.ESCALATED

    def test_transition_validation(self):
        incident = monitor_open_incident(make_monitor(), "risk_engine")
        # OPEN → RESOLVED is a legal transition.
        incident.transition(HealthIncidentState.RESOLVED)
        # RESOLVED is terminal — no outgoing transitions.
        with pytest.raises(HealthIncidentTransitionError):
            incident.transition(HealthIncidentState.OPEN)
        # Backwards transitions are not allowed.
        incident2 = monitor_open_incident(make_monitor(), "risk_engine")
        with pytest.raises(HealthIncidentTransitionError):
            incident2.transition(HealthIncidentState.DETECTED)

    def test_severity_by_criticality(self):
        low = make_monitor(
            [HealthProfile(component_id="analytics", criticality=ComponentCriticality.NON_CRITICAL)]
        )
        low.open_incident("analytics", "X", now=NOW)
        assert low.incident("analytics").severity == "LOW"

        op = make_monitor(
            [HealthProfile(component_id="position", criticality=ComponentCriticality.OPERATIONAL)]
        )
        op.open_incident("position", "DATA_STALE", now=NOW)
        assert op.incident("position").severity == "HIGH"


def monitor_open_incident(monitor, component_id, reason="TEST"):
    return monitor.open_incident(component_id, reason=reason, now=NOW)


class TestDependencyAwareHealth:
    def test_unhealthy_dependency_degrades_risk(self):
        monitor = make_monitor(
            [risk_profile(required_dependencies=("position_service",))]
        )
        monitor.record_heartbeat(hb(timestamp=NOW - timedelta(seconds=2)))
        evaluation = monitor.evaluate(
            "risk_engine",
            now=NOW,
            dependencies=[DependencyStatus("position_service", HealthStatus.UNHEALTHY)],
        )
        assert evaluation.status is HealthStatus.DEGRADED
        assert "DEPENDENCY_UNHEALTHY" in evaluation.reasons


class TestDataFreshnessAwareHealth:
    def test_stale_data_degrades(self):
        monitor = make_monitor(
            [
                HealthProfile(
                    component_id="market_data",
                    criticality=ComponentCriticality.OPERATIONAL,
                    freshness_policy=FreshnessPolicy("market_data", fresh_seconds=5, stale_seconds=15),
                )
            ]
        )
        monitor.record_heartbeat(
            hb(component_id="market_data", timestamp=NOW - timedelta(seconds=2))
        )
        monitor.record_data_update("market_data", NOW - timedelta(seconds=10))
        evaluation = monitor.evaluate("market_data", now=NOW)
        assert evaluation.status is HealthStatus.DEGRADED
        assert "DATA_STALE" in evaluation.reasons

    def test_expired_data_is_unhealthy(self):
        monitor = make_monitor(
            [
                HealthProfile(
                    component_id="market_data",
                    criticality=ComponentCriticality.OPERATIONAL,
                    freshness_policy=FreshnessPolicy("market_data", fresh_seconds=5, stale_seconds=15),
                )
            ]
        )
        monitor.record_heartbeat(
            hb(component_id="market_data", timestamp=NOW - timedelta(seconds=2))
        )
        monitor.record_data_update("market_data", NOW - timedelta(seconds=20))
        evaluation = monitor.evaluate("market_data", now=NOW)
        assert evaluation.status is HealthStatus.UNHEALTHY
        assert "DATA_EXPIRED" in evaluation.reasons


class TestConsumerLagAwareHealth:
    def test_high_lag_degrades(self):
        monitor = make_monitor(
            [risk_profile(consumer_lag_warning=1000, consumer_lag_critical=10000)]
        )
        monitor.record_heartbeat(hb(timestamp=NOW - timedelta(seconds=2)))
        evaluation = monitor.evaluate("risk_engine", now=NOW, consumer_lag=5000)
        assert evaluation.status is HealthStatus.DEGRADED
        assert "CONSUMER_LAG_HIGH" in evaluation.reasons

    def test_critical_lag_is_unhealthy(self):
        monitor = make_monitor(
            [risk_profile(consumer_lag_warning=1000, consumer_lag_critical=10000)]
        )
        monitor.record_heartbeat(hb(timestamp=NOW - timedelta(seconds=2)))
        evaluation = monitor.evaluate("risk_engine", now=NOW, consumer_lag=50000)
        assert evaluation.status is HealthStatus.UNHEALTHY
        assert "CONSUMER_LAG_CRITICAL" in evaluation.reasons


class TestStartupGracePeriod:
    def test_grace_period_prevents_unhealthy(self):
        monitor = make_monitor()
        monitor.mark_started("risk_engine", NOW - timedelta(seconds=10))
        evaluation = monitor.evaluate("risk_engine", now=NOW)
        assert evaluation.status is HealthStatus.UNKNOWN
        assert monitor.health_status("risk_engine") is HealthStatus.UNKNOWN

    def test_grace_expired_without_heartbeat_is_unhealthy(self):
        monitor = make_monitor()
        monitor.mark_started("risk_engine", NOW - timedelta(seconds=60))
        evaluation = monitor.evaluate("risk_engine", now=NOW)
        assert evaluation.status is HealthStatus.UNHEALTHY


class TestEventSink:
    def test_on_event_receives_emitted_events(self):
        collected = []
        monitor = make_monitor(on_event=collected.append)
        monitor.record_heartbeat(hb(timestamp=NOW - timedelta(seconds=20)))
        monitor.evaluate("risk_engine", now=NOW)
        assert any(isinstance(e, HeartbeatMissed) for e in collected)
        assert any(isinstance(e, HealthStatusChanged) for e in collected)
