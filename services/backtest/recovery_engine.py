"""
Recovery engine.
"""


class RecoveryEngine:

    def __init__(
        self,
        persistence,
        checkpoint_manager,
    ):

        self.persistence = persistence

        self.checkpoint_manager = checkpoint_manager

    def recover(
        self,
        context,
    ):

        snapshot = self.checkpoint_manager.load(
            context.snapshot_id
        )

        if snapshot is None:

            return None

        self.persistence.persist(
            context.workflow_id,
            snapshot.state,
        )

        return snapshot.state