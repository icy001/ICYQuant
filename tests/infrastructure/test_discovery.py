from infrastructure.discovery import (
    ServiceInstance,
    ServiceRegistry,
)


def test_service_registry():

    registry = ServiceRegistry()

    registry.register(
        ServiceInstance(
            "risk-engine",
            "localhost",
            9001
        )
    )

    result = registry.get(
        "risk-engine"
    )

    assert len(result) == 1