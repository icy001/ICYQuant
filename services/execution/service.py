class ExecutionService:

    def __init__(
        self,
        manager,
    ):
        self.manager = manager

    def submit(
        self,
        broker,
        request,
    ):
        return self.manager.execute(
            broker,
            request
        )