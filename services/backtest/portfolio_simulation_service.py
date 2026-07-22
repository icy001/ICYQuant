"""
Portfolio simulation service.
"""


class PortfolioSimulationService:

    def __init__(
        self,
        simulator,
    ):

        self.simulator = simulator


    def snapshot(
        self,
        market_value,
    ):

        return self.simulator.snapshot(
            market_value,
        )