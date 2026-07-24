from production_platform.runtime import *


def test_service_runtime():

    service = Service(

        "order-engine",

        "v1"

    )


    manager = RuntimeManager(

        RuntimeContainer()

    )


    manager.start_service(service)


    assert service.status == "RUNNING"