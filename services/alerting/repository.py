class AlertRepository:

    def __init__(self):
        self.alerts = []

    def save(self, alert):
        self.alerts.append(alert)

    def all(self):
        return self.alerts
