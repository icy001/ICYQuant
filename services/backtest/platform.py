"""
Backtesting platform.
"""


class BacktestPlatform:
    def __init__(
        self,
        components,
    ):
        self.components = components

    def start(self):
        return True