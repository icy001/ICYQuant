"""
Order execution gateway.
"""


class OrderExecutionGateway:

    def __init__(
        self,
        broker,
    ):
        self.broker = broker

    def execute(
        self,
        order,
    ):
        return self.broker.submit_order(
            order
        )