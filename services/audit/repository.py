class AuditRepository:
    def __init__(self):
        self.events = []

    def append(self, event):
        self.events.append(event)

    def query_all(self):
        return self.events