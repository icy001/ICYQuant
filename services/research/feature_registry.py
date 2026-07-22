"""
Feature registry.
"""


class FeatureRegistry:

    def __init__(self):

        self._features = {}

    def register(
        self,
        feature,
    ):

        self._features[
            feature.feature_id
        ] = feature

    def get(
        self,
        feature_id,
    ):

        return self._features.get(
            feature_id
        )

    def list_all(self):

        return list(
            self._features.values()
        )