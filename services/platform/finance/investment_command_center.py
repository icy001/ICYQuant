"""
Investment command center.
"""


class InvestmentCommandCenter:

    def __init__(
        self,
        world_model,
        simulator,
    ):

        self.world = world_model

        self.simulator = simulator

    def evaluate(
        self,
        scenario,
    ):

        return self.simulator.simulate(
            scenario
        )