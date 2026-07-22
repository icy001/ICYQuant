"""
Market shock simulator.
"""


class MarketShockSimulator:

    def apply(
        self,
        value,
        shock,
    ):

        return value * (
            1 + shock
        )