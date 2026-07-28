class AlertingService:

    def __init__(
        self,
        repository,
        dispatcher
    ):
        self.repository = repository
        self.dispatcher = dispatcher

    def publish(self, alert):
        self.repository.save(alert)

        return self.dispatcher.dispatch(alert)
