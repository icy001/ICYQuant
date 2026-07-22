"""
Feature storage.
"""


class FeatureStorage:

    def __init__(self):

        self._storage = {}

    def save(
        self,
        feature_id,
        values,
    ):

        self._storage[
            feature_id
        ] = values

    def load(
        self,
        feature_id,
    ):

        return self._storage.get(
            feature_id
        )