"""
Snapshot repository.
"""


class SnapshotRepository:
    def __init__(self):
        self.snapshots = {}

    def save(
        self,
        snapshot,
    ):
        self.snapshots[snapshot.snapshot_id] = snapshot

    def load(
        self,
        snapshot_id,
    ):
        return self.snapshots.get(snapshot_id)