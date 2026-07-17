"""
Pipeline orchestration service.
"""


class PipelineService:
    def __init__(
        self,
        scheduler,
    ):
        self.scheduler = scheduler

    def run(
        self,
        dag,
    ):
        return self.scheduler.schedule(dag)