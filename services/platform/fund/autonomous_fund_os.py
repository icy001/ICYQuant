"""
Autonomous hedge fund operating system.
"""


class AutonomousFundOS:

    def __init__(
        self,
        command_center,
    ):
        self.command_center = command_center

    def run(
        self,
        market,
    ):
        return self.command_center.operate(
            market
        )