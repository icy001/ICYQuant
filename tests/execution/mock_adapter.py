from services.execution import *


class MockBroker(BrokerAdapter):

    def execute(
        self,
        request,
    ):
        return ExecutionResult(
            request.order_id,
            request.quantity,
            150.5,
            "FILLED"
        )