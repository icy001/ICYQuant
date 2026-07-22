"""
Feature version manager.
"""


class FeatureVersionManager:

    def __init__(self):

        self._versions = {}

    def publish(
        self,
        feature_id,
        version,
    ):

        self._versions[
            feature_id
        ] = version

    def current(
        self,
        feature_id,
    ):

        return self._versions.get(
            feature_id
        )