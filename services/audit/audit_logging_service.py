class AuditLoggingService:
    def __init__(self, manager):
        self.manager = manager

    def record(self, event):
        return self.manager.record(event)

    def history(self):
        return self.manager.history()