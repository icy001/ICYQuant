"""
Distributed backtest engine.
"""


class DistributedBacktestEngine:

    def __init__(
        self,
        scheduler,
        resource_manager,
        aggregator,
    ):

        self.scheduler = scheduler

        self.resource_manager = resource_manager

        self.aggregator = aggregator


    def run(
        self,
        executor,
    ):

        workers = self.resource_manager.list_workers()

        if not workers:

            return []


        index = 0

        while True:

            task = self.scheduler.next_task()

            if task is None:

                break

            worker = workers[
                index % len(workers)
            ]

            result = worker.execute(
                task,
                executor,
            )

            self.aggregator.collect(
                result
            )

            index += 1

        return self.aggregator.aggregate()