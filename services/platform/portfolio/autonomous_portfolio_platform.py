"""
Autonomous portfolio platform.
"""


class AutonomousPortfolioPlatform:

    def __init__(
        self,
        command_center,
    ):

        self.center = command_center

    def manage(
        self,
        portfolio,
    ):

        return self.center.execute(
            portfolio
        )