"""
Strategy registry.
"""


class StrategyRegistry:

    def __init__(self):

        self._strategies = {}


    def register(
        self,
        registration,
        runner,
    ):

        self._strategies[
            registration.strategy_id
        ] = (
            registration,
            runner,
        )


    def get(
        self,
        strategy_id,
    ):

        return self._strategies.get(
            strategy_id
        )


    def list_all(self):

        return list(
            self._strategies.values()
        )