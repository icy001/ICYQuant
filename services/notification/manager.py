class NotificationManager:
    def __init__(self, repository, engine, router):
        self.repository = repository
        self.engine = engine
        self.router = router

    def send(self, notification):
        self.repository.save(notification)
        self.router.route(notification.channel)
        return notification