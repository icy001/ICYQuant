"""Backward-compatible tests for legacy monitoring API."""

from services.monitoring import MonitoringCenter, MonitoringService, HealthStatus


def test_monitoring_service_legacy():
    """Legacy test updated for new MonitoringCenter API."""
    # New MonitoringService = MonitoringCenter (no-arg constructor)
    service = MonitoringService()
    assert service is not None
    assert service.health is not None
    assert service.collector is not None

    # Health check via new API
    service.health.register(
        "test_service",
        lambda: (__import__("services.monitoring.health.service_health", fromlist=["ServiceStatus"]).ServiceStatus.HEALTHY, 15.0, "ok"),
    )
    report = service.health.check_all()
    assert report.overall_status.value == "Healthy"

    # Record a metric via new API
    service.record_metric("api_latency", 20.0)
    snapshot = service.collector.snapshot()
    assert snapshot["custom_gauges"]["api_latency"] == 20.0

    # Verify backward compatibility
    assert HealthStatus.UP == "UP"
    assert HealthStatus.DOWN == "DOWN"
    assert HealthStatus.DEGRADED == "DEGRADED"
