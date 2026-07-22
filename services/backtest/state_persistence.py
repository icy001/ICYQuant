"""
State persistence layer.
"""


class StatePersistence:

    def __init__(self):

        self._storage = {}

    def persist(
        self,
        workflow_id,
        state,
    ):

        self._storage[
            workflow_id
        ] = state

    def restore(
        self,
        workflow_id,
    ):

        return self._storage.get(
            workflow_id
        )