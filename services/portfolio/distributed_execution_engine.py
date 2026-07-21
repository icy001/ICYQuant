"""
Distributed execution engine.
"""


class DistributedExecutionEngine:

    def __init__(
        self,
        executor,
        aggregator,
    ):

        self.executor = executor

        self.aggregator = aggregator

    def execute(
        self,
        tasks,
    ):

        results = []

        for task in tasks:

            results.append(
                self.executor.execute(
                    task,
                )
            )

        return self.aggregator.aggregate(
            results,
        )