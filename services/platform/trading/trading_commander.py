"""
AI Trading Commander.
"""


class TradingCommander:

    def __init__(
        self,
        order_agent,
        router,
        optimizer,
    ):

        self.agent = order_agent

        self.router = router

        self.optimizer = optimizer

    def execute(
        self,
        signal,
        risk,
    ):

        decision = self.agent.decide(
            signal,
            risk
        )

        order = self.router.route(
            decision,
            ["PRIMARY"]
        )

        return self.optimizer.optimize(
            order,
            {}
        )