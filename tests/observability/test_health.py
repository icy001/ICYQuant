from services.observability import (
    healthy,
    HealthStatus,
)


def test_health_status():
    result = healthy(
        "database"
    )
    assert (
        result.status
        ==
        HealthStatus.HEALTHY
    )