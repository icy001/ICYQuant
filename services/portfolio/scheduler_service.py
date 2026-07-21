"""
Scheduler service.
"""


class SchedulerService:

    def __init__(
        self,
        scheduler,
    ):

        self.scheduler = scheduler

    def schedule(
        self,
        nodes,
    ):

        return self.scheduler.schedule(
            nodes,
        )