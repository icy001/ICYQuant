class AuditRecorder:
    def record(self, repository, event):
        repository.append(event)
        return event