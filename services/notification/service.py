class NotificationService:
    def __init__(self, manager):
        self.manager = manager

    def notify(self, notification):
        return self.manager.send(notification)