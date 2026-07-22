"""
Virtual execution engine.
"""


class ExecutionEngine:

    def __init__(
        self,
        simulator,
    ):

        self.simulator = simulator


    def execute(
        self,
        order,
        slippage_rate,
        commission_rate,
    ):

        return self.simulator.execute(
            order,
            slippage_rate,
            commission_rate,
        )