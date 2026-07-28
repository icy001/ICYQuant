class NotificationRepository:
    def __init__(self):
        self.notifications = {}

    def save(self, notification):
        self.notifications[notification.notification_id] = notification

    def get(self, notification_id):
        return self.notifications.get(notification_id)