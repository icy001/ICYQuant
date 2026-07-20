"""
Backtest component registry.
"""


class BacktestComponentRegistry:
    def __init__(self):
        self.components = {}

    def register(
        self,
        name,
        component,
    ):
        self.components[name] = component

    def get(
        self,
        name,
    ):
        return self.components[name]