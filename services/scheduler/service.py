class SchedulerService:

    def __init__(
        self,
        repository,
        engine
    ):
        self.repository = repository
        self.engine = engine

    def submit(
        self,
        job
    ):
        self.repository.save(job)

        return self.engine.execute(job)
