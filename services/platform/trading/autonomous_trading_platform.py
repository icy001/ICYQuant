"""
Autonomous trading platform.
"""


class AutonomousTradingPlatform:

    def __init__(
        self,
        center,
    ):

        self.center = center

    def run(
        self,
        signal,
        risk,
    ):

        return self.center.trade(
            signal,
            risk
        )