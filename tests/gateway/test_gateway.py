from services.gateway import *


def test_gateway_load_balancer():
    router = Router()

    router.add(
        Route(
            "/orders",
            "ORDER_SERVICE"
        )
    )

    service = GatewayService(
        GatewayManager(
            router,
            LoadBalancer(
                RoundRobinStrategy(),
                HealthFilter()
            )
        )
    )

    instances = [
        BackendInstance(
            "127.0.0.1",
            8001
        ),
        BackendInstance(
            "127.0.0.2",
            8002
        )
    ]

    result = service.forward(
        "/orders",
        instances
    )

    assert result is not None
