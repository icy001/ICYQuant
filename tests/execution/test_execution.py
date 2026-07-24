from services.execution import *

from .mock_adapter import MockBroker


def test_execution_gateway():

    router = ExecutionRouter()

    router.register(
        "mock",
        MockBroker()
    )

    tracker = ExecutionTracker()

    manager = ExecutionManager(
        router,
        tracker
    )

    service = ExecutionService(
        manager
    )

    request = ExecutionRequest(
        "ORD001",
        "NVDA",
        10,
        "BUY",
        "LIMIT"
    )

    result = service.submit(
        "mock",
        request
    )

    assert result.status == "FILLED"