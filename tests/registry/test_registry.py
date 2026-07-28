from services.registry import *


def test_service_registry():
    repository = ServiceRepository()

    service = ServiceRegistryService(
        RegistrationManager(
            repository
        ),
        DiscoveryEngine(
            repository
        )
    )

    instance = ServiceInstance(
        "S001",
        "ORDER_SERVICE",
        "127.0.0.1",
        8001,
        ServiceStatus.UP
    )

    service.register(instance)

    result = service.discover("ORDER_SERVICE")

    assert len(result.instances) == 1
