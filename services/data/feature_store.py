"""
Offline / Online feature store.
"""


class FeatureStore:

    def __init__(self):

        self._storage = {}

    def put(
        self,
        entity,
        feature,
        value,
    ):

        self._storage.setdefault(
            entity,
            {}
        )[feature] = value

    def get(
        self,
        entity,
        feature,
    ):

        return self._storage.get(
            entity,
            {}
        ).get(
            feature,
        )