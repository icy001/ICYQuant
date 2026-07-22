"""
Multi-strategy coordinator.
"""


class MultiStrategyCoordinator:

    def __init__(
        self,
        registry,
    ):

        self.registry = registry


    def execute(
        self,
        tick,
    ):

        results = {}

        for registration, runner in self.registry.list_all():

            results[
                registration.strategy_id
            ] = runner.run(
                tick
            )

        return results