from .snapshot_manager import SnapshotManager
from .recovery import RecoveryManager


class WorkflowPersistenceService:

    def __init__(self, repository):
        self.repository = repository
        self.snapshot = SnapshotManager()
        self.recovery = RecoveryManager()

    def save(self, instance):
        self.repository.save_instance(instance)

        return instance

    def save_snapshot(self, snapshot):
        self.repository.save_snapshot(snapshot)

        return snapshot

    def load_snapshot(self, workflow_id):
        return self.repository.get_snapshot(workflow_id)
