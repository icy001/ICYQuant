"""Unit tests: Readiness evaluation, dependency health, data freshness,
consumer lag."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.control_plane.health.health_status import HealthStatus
from services.control_plane.health.readiness import (
    DataFreshness,
    DependencyStatus,
    FreshnessPolicy,
    ReadinessStatus,
    evaluate_readiness,
)

NOW = datetime(2026, 8, 12, 10, 0, 0, tzinfo=timezone.utc)


def dep(component_id, status=HealthStatus.HEALTHY):
    return DependencyStatus(component_id=component_id, status=status)


class TestReadinessStatus:
    def test_values(self):
        assert [s.value for s in ReadinessStatus] == [
            "READY",
            "NOT_READY",
            "FAILED",
            "UNKNOWN",
        ]

    def test_is_ready(self):
        assert ReadinessStatus.READY.is_ready
        assert not ReadinessStatus.NOT_READY.is_ready


class TestDependencyHealth:
    def test_all_healthy_is_ready(self):
        result = evaluate_readiness(
            "risk_engine",
            dependencies=[dep("position"), dep("market_data")],
            now=NOW,
        )
        assert result.status is ReadinessStatus.READY

    def test_unhealthy_dependency_is_not_ready(self):
        result = evaluate_readiness(
            "risk_engine",
            dependencies=[dep("position", HealthStatus.UNHEALTHY)],
            now=NOW,
        )
        assert result.status is ReadinessStatus.NOT_READY
        assert "DEPENDENCY_UNHEALTHY" in result.reasons

    def test_degraded_dependency_is_not_ready(self):
        result = evaluate_readiness(
            "risk_engine",
            dependencies=[dep("event_bus", HealthStatus.DEGRADED)],
            now=NOW,
        )
        assert result.status is ReadinessStatus.NOT_READY
        assert "DEPENDENCY_DEGRADED" in result.reasons

    def test_missing_dependency_defaults_unknown(self):
        result = evaluate_readiness("risk_engine", dependencies=[dep("db")], now=NOW)
        assert result.status is ReadinessStatus.READY  # UNKNOWN dep is neutral

    def test_no_dependencies_is_ready(self):
        result = evaluate_readiness("risk_engine", now=NOW)
        assert result.status is ReadinessStatus.READY


class TestDataFreshness:
    def test_freshness_values(self):
        assert [f.value for f in DataFreshness] == [
            "FRESH",
            "STALE",
            "EXPIRED",
            "UNKNOWN",
        ]

    def test_fresh_within_window(self):
        policy = FreshnessPolicy("position", fresh_seconds=5, stale_seconds=15)
        assert (
            policy.evaluate(NOW - timedelta(seconds=2), now=NOW) is DataFreshness.FRESH
        )

    def test_stale_between_windows(self):
        policy = FreshnessPolicy("position", fresh_seconds=5, stale_seconds=15)
        assert (
            policy.evaluate(NOW - timedelta(seconds=10), now=NOW) is DataFreshness.STALE
        )

    def test_expired_beyond_stale(self):
        policy = FreshnessPolicy("position", fresh_seconds=5, stale_seconds=15)
        assert (
            policy.evaluate(NOW - timedelta(seconds=20), now=NOW)
            is DataFreshness.EXPIRED
        )

    def test_unknown_without_last_update(self):
        policy = FreshnessPolicy("position", fresh_seconds=5, stale_seconds=15)
        assert policy.evaluate(None, now=NOW) is DataFreshness.UNKNOWN


class TestFreshnessAffectsReadiness:
    def test_stale_data_not_ready(self):
        result = evaluate_readiness(
            "position", freshness=DataFreshness.STALE, now=NOW
        )
        assert result.status is ReadinessStatus.NOT_READY
        assert "DATA_STALE" in result.reasons

    def test_expired_data_failed(self):
        result = evaluate_readiness(
            "position", freshness=DataFreshness.EXPIRED, now=NOW
        )
        assert result.status is ReadinessStatus.FAILED
        assert "DATA_EXPIRED" in result.reasons

    def test_fresh_data_is_ready(self):
        result = evaluate_readiness(
            "position", freshness=DataFreshness.FRESH, now=NOW
        )
        assert result.status is ReadinessStatus.READY


class TestConsumerLag:
    def test_low_lag_is_ready(self):
        result = evaluate_readiness(
            "event_bus",
            consumer_lag=0,
            consumer_lag_warning=1000,
            consumer_lag_critical=10000,
            now=NOW,
        )
        assert result.status is ReadinessStatus.READY

    def test_high_lag_not_ready(self):
        result = evaluate_readiness(
            "event_bus",
            consumer_lag=5000,
            consumer_lag_warning=1000,
            consumer_lag_critical=10000,
            now=NOW,
        )
        assert result.status is ReadinessStatus.NOT_READY
        assert "CONSUMER_LAG_HIGH" in result.reasons

    def test_critical_lag_failed(self):
        result = evaluate_readiness(
            "event_bus",
            consumer_lag=50000,
            consumer_lag_warning=1000,
            consumer_lag_critical=10000,
            now=NOW,
        )
        assert result.status is ReadinessStatus.FAILED
        assert "CONSUMER_LAG_CRITICAL" in result.reasons


class TestReadinessEvaluation:
    def test_serialization(self):
        result = evaluate_readiness(
            "risk_engine",
            dependencies=[dep("position", HealthStatus.UNHEALTHY)],
            freshness=DataFreshness.STALE,
            now=NOW,
        )
        data = result.to_dict()
        assert data["component_id"] == "risk_engine"
        assert data["status"] == "NOT_READY"
        assert data["freshness"] == "STALE"
        assert data["dependencies"][0]["status"] == "UNHEALTHY"
