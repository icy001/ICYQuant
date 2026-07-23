from infrastructure.communication import (
    ServiceRequest,
)


def test_request():

    request = ServiceRequest(
        "risk-engine",
        "calculate",
        {}
    )

    assert request.service == "risk-engine"