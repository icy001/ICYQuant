"""
Execution optimization engine.
"""


class ExecutionOptimizer:

    def optimize(
        self,
        order,
        market,
    ):

        return {
            "order":
                order,
            "execution_mode":
                "optimal",
        }