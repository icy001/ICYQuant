from services.monitoring import *


def test_monitoring_service():
    service = MonitoringService(
        MonitoringManager(
            MonitoringRepository(),
            MetricsCollector(),
            HealthChecker()
        )
    )

    metric = Metric(
        "api_latency",
        20,
        1000
    )

    result = service.record_metric(metric)

    assert result.value == 20

    assert service.check_health(20) == HealthStatus.UP