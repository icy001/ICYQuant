class ExecutionManager:

    def __init__(
        self,
        router,
        tracker,
    ):
        self.router = router
        self.tracker = tracker

    def execute(
        self,
        broker,
        request,
    ):
        result = self.router.route(
            broker,
            request
        )

        self.tracker.record(
            result
        )

        return result