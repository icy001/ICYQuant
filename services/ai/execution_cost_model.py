"""
Execution cost estimator.
"""


class ExecutionCostModel:

    def estimate(
        self,
        quantity,
        spread,
        fee,
    ):

        return quantity * spread + fee