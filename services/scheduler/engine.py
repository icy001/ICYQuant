class SchedulerEngine:

    def __init__(
        self,
        worker
    ):
        self.worker = worker

    def execute(
        self,
        job
    ):
        return self.worker.run(job)
