"""
Checkpoint manager.
"""


class CheckpointManager:

    def __init__(self):

        self._checkpoints = {}

    def save(
        self,
        snapshot,
    ):

        self._checkpoints[
            snapshot.snapshot_id
        ] = snapshot

    def load(
        self,
        snapshot_id,
    ):

        return self._checkpoints.get(
            snapshot_id
        )