class AuditManager:
    def __init__(self, repository, validator, recorder):
        self.repository = repository
        self.validator = validator
        self.recorder = recorder

    def record(self, event):
        if not self.validator.validate(event):
            raise ValueError("Invalid audit event")

        return self.recorder.record(self.repository, event)

    def history(self):
        return self.repository.query_all()