class WorkflowService:

    def __init__(
        self,
        engine,
        repository
    ):
        self.engine = engine
        self.repository = repository

    def start(
        self,
        workflow
    ):
        self.repository.save(
            workflow
        )

        return self.engine.run(
            workflow
        )
