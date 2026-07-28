from services.service_mesh import *


def test_service_mesh():

    registry = MeshRegistry()

    registry.register(
        ServiceEndpoint(
            "RISK_SERVICE",
            "127.0.0.1",
            9001
        )
    )

    service = ServiceMeshService(
        registry,
        RoutingController(),
        SecurityManager()
    )

    result = service.connect(
        "RISK_SERVICE"
    )

    assert result.name == "RISK_SERVICE"
