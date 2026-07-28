class BackupManager:
    def __init__(self, repository):
        self.repository = repository

    def create(self, snapshot):
        self.repository.save(snapshot)
        return snapshot
