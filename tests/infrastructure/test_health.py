from infrastructure.health import (
    HealthChecker,
)


def test_health():

    checker = HealthChecker()

    result = checker.check(
        "order-service"
    )

    assert result["status"] == "healthy"