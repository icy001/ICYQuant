from services.discovery import *


def test_discovery():
    service = DiscoveryService(
        DiscoveryRepository()
    )

    instance = ServiceInstance(
        "order-service",
        "node-001",
        "127.0.0.1",
        8080
    )

    service.register(instance)

    assert service.healthy(instance)
