"""Tests for Service Health, Dependency Health, and Readiness Probes."""

from services.monitoring.health.service_health import (
    ServiceHealthMonitor,
    ServiceStatus,
    HealthReport,
)
from services.monitoring.health.dependency_health import (
    DependencyChecker,
    DependencyStatus,
)
from services.monitoring.health.readiness import (
    ReadinessProbe,
    ProbeType,
)


# =========================================================================
# Service Health Monitor Tests
# =========================================================================


class TestServiceHealthMonitor:
    """Tests for ServiceHealthMonitor."""

    def test_register_and_check_single_service(self):
        monitor = ServiceHealthMonitor()
        monitor.register(
            "OMS",
            lambda: (ServiceStatus.HEALTHY, 12.5, "OMS is running"),
        )
        result = monitor.check("OMS")
        assert result["service"] == "OMS"
        assert result["status"] == ServiceStatus.HEALTHY.value
        assert result["latency_ms"] == 12.5
        assert result["uptime_pct"] == 100.0

    def test_check_unregistered_service(self):
        monitor = ServiceHealthMonitor()
        result = monitor.check("unknown_service")
        assert result["status"] == ServiceStatus.UNKNOWN.value
        assert "not registered" in result["message"]

    def test_check_all_multiple_services(self):
        monitor = ServiceHealthMonitor()
        monitor.register("OMS", lambda: (ServiceStatus.HEALTHY, 10.0, "ok"))
        monitor.register("Risk", lambda: (ServiceStatus.HEALTHY, 15.0, "ok"))
        monitor.register("Portfolio", lambda: (ServiceStatus.HEALTHY, 8.0, "ok"))

        report = monitor.check_all()
        assert isinstance(report, HealthReport)
        assert report.overall_status == ServiceStatus.HEALTHY
        assert len(report.services) == 3

    def test_overall_degraded_when_one_service_degraded(self):
        monitor = ServiceHealthMonitor()
        monitor.register("OMS", lambda: (ServiceStatus.HEALTHY, 10.0, "ok"))
        monitor.register("Risk", lambda: (ServiceStatus.DEGRADED, 150.0, "slow"))

        report = monitor.check_all()
        assert report.overall_status == ServiceStatus.DEGRADED

    def test_overall_unhealthy_when_one_service_unhealthy(self):
        monitor = ServiceHealthMonitor()
        monitor.register("OMS", lambda: (ServiceStatus.HEALTHY, 10.0, "ok"))
        monitor.register("Risk", lambda: (ServiceStatus.UNHEALTHY, 0.0, "down"))

        report = monitor.check_all()
        assert report.overall_status == ServiceStatus.UNHEALTHY

    def test_check_raises_exception_caught(self):
        monitor = ServiceHealthMonitor()

        def broken_check():
            raise RuntimeError("boom")

        monitor.register("Broken", broken_check)
        result = monitor.check("Broken")
        assert result["status"] == ServiceStatus.UNHEALTHY.value
        assert "RuntimeError" in result["message"] or "boom" in result["message"]

    def test_uptime_tracking(self):
        monitor = ServiceHealthMonitor()
        monitor.register("OMS", lambda: (ServiceStatus.HEALTHY, 10.0, "ok"))

        # Check multiple times
        for _ in range(5):
            monitor.check("OMS")

        result = monitor.check("OMS")
        assert result["uptime_pct"] == 100.0

    def test_uptime_drops_with_failures(self):
        monitor = ServiceHealthMonitor()
        call_count = [0]

        def alternating_check():
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                return (ServiceStatus.UNHEALTHY, 0.0, "down")
            return (ServiceStatus.HEALTHY, 10.0, "ok")

        monitor.register("FlipFlop", alternating_check)
        for _ in range(10):
            monitor.check("FlipFlop")

        result = monitor.check("FlipFlop")
        # ~50% uptime
        assert 40.0 <= result["uptime_pct"] <= 60.0

    def test_summary_dict(self):
        monitor = ServiceHealthMonitor()
        monitor.register("OMS", lambda: (ServiceStatus.HEALTHY, 10.0, "ok"))
        report = monitor.check_all()
        summary = report.summary()
        assert summary["overall"] == "Healthy"
        assert summary["healthy_count"] == 1
        assert summary["total_count"] == 1

    def test_to_dict(self):
        monitor = ServiceHealthMonitor()
        monitor.register("OMS", lambda: (ServiceStatus.HEALTHY, 10.0, "ok"))
        report = monitor.check_all()
        d = report.to_dict()
        assert d["overall_status"] == "Healthy"
        assert "OMS" in d["services"]


# =========================================================================
# Dependency Health Tests
# =========================================================================


class TestDependencyChecker:
    """Tests for DependencyChecker."""

    def test_register_and_check_dependency(self):
        checker = DependencyChecker()
        checker.register("redis", lambda: True)
        result = checker.check("redis")
        assert result["dependency"] == "redis"
        assert result["status"] == DependencyStatus.AVAILABLE.value

    def test_check_unavailable_dependency(self):
        checker = DependencyChecker()
        checker.register("redis", lambda: False)
        result = checker.check("redis")
        assert result["status"] == DependencyStatus.UNAVAILABLE.value
        assert result["consecutive_failures"] == 1

    def test_check_raises_exception(self):
        checker = DependencyChecker()

        def broken():
            raise RuntimeError("boom")

        checker.register("kafka", broken)
        result = checker.check("kafka")
        assert result["status"] == DependencyStatus.UNAVAILABLE.value

    def test_check_all_available(self):
        checker = DependencyChecker()
        checker.register("redis", lambda: True)
        checker.register("kafka", lambda: True)
        checker.register("postgres", lambda: True)

        report = checker.check_all()
        assert report.overall == DependencyStatus.AVAILABLE
        assert len(report.dependencies) == 3

    def test_check_all_with_unavailable(self):
        checker = DependencyChecker()
        checker.register("redis", lambda: True)
        checker.register("kafka", lambda: False)

        report = checker.check_all()
        assert report.overall == DependencyStatus.UNAVAILABLE

    def test_is_available_shortcut(self):
        checker = DependencyChecker()
        checker.register("redis", lambda: True)
        assert checker.is_available("redis") is True

        checker.register("kafka", lambda: False)
        assert checker.is_available("kafka") is False

    def test_unregistered_dependency(self):
        checker = DependencyChecker()
        result = checker.check("nonexistent")
        assert result["status"] == DependencyStatus.UNKNOWN.value
        assert result["message"] == "Not registered"

    def test_consecutive_failures_reset_on_success(self):
        checker = DependencyChecker()
        checker.register("redis", lambda: False)
        checker.check("redis")
        checker.check("redis")
        result = checker.check("redis")
        assert result["consecutive_failures"] == 3

    def test_latency_tracking(self):
        checker = DependencyChecker()
        checker.register("redis", lambda: True)
        result = checker.check("redis")
        assert result["latency_ms"] >= 0
        assert result["avg_latency_ms"] >= 0


# =========================================================================
# Readiness Probe Tests
# =========================================================================


class TestReadinessProbe:
    """Tests for ReadinessProbe."""

    def test_mark_started_and_uptime(self):
        probe = ReadinessProbe()
        probe.mark_started()
        assert probe.uptime_seconds() >= 0

    def test_add_and_run_liveness_probe(self):
        probe = ReadinessProbe()
        probe.add_check(ProbeType.LIVENESS, "process_alive", lambda: True)
        result = probe.run(ProbeType.LIVENESS)
        assert result.ready is True
        assert len(result.checks) == 1
        assert len(result.failures) == 0

    def test_readiness_with_failure(self):
        probe = ReadinessProbe()
        probe.add_check(ProbeType.READINESS, "db", lambda: True)
        probe.add_check(ProbeType.READINESS, "cache", lambda: False)

        result = probe.run(ProbeType.READINESS)
        assert result.ready is False
        assert "cache" in result.failures

    def test_startup_probe(self):
        probe = ReadinessProbe()
        probe.add_check(ProbeType.STARTUP, "init", lambda: True)
        result = probe.run(ProbeType.STARTUP)
        assert result.ready is True

    def test_is_ready_shortcut(self):
        probe = ReadinessProbe()
        probe.add_check(ProbeType.READINESS, "db", lambda: True)
        assert probe.is_ready() is True

    def test_is_alive_shortcut(self):
        probe = ReadinessProbe()
        probe.add_check(ProbeType.LIVENESS, "process", lambda: True)
        assert probe.is_alive() is True

    def test_startup_complete_shortcut(self):
        probe = ReadinessProbe()
        probe.add_check(ProbeType.STARTUP, "init", lambda: True)
        assert probe.startup_complete() is True

    def test_result_to_dict(self):
        probe = ReadinessProbe()
        probe.add_check(ProbeType.READINESS, "db", lambda: True)
        result = probe.run(ProbeType.READINESS)
        d = result.to_dict()
        assert d["ready"] is True
        assert d["probe_type"] == "readiness"
        assert "duration_ms" in d

    def test_multiple_checks_one_fails(self):
        probe = ReadinessProbe()
        probe.add_check(ProbeType.READINESS, "a", lambda: True)
        probe.add_check(ProbeType.READINESS, "b", lambda: True)
        probe.add_check(ProbeType.READINESS, "c", lambda: False)

        result = probe.run(ProbeType.READINESS)
        assert result.ready is False
        assert len(result.failures) == 1

    def test_exception_in_check(self):
        probe = ReadinessProbe()

        def raises():
            raise RuntimeError("fail")

        probe.add_check(ProbeType.LIVENESS, "broken", raises)
        result = probe.run(ProbeType.LIVENESS)
        assert result.ready is False
        assert "broken" in result.failures

    def test_uptime_zero_before_mark_started(self):
        probe = ReadinessProbe()
        assert probe.uptime_seconds() == 0.0
