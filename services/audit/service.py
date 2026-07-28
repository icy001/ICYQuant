class AuditService:
    def __init__(self, repository):
        self.repository = repository

    def record(self, event):
        self.repository.save(event)

    def history(self):
        return self.repository.query()
