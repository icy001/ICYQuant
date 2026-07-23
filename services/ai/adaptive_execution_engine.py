"""
Adaptive execution engine.
"""


class AdaptiveExecutionEngine:

    def __init__(
        self,
        router,
        optimizer,
    ):

        self.router = router

        self.optimizer = optimizer

    def execute(
        self,
        order,
        venues,
    ):

        venue = self.router.route(
            order,
            venues,
        )

        return self.optimizer.optimize(
            {
                "venue": venue,
                "order": order,
            }
        )