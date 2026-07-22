"""
Feature query service.
"""


class FeatureQueryService:

    def __init__(
        self,
        registry,
        storage,
    ):

        self.registry = registry

        self.storage = storage

    def query(
        self,
        feature_id,
    ):

        return {
            "feature":
                self.registry.get(
                    feature_id
                ),
            "values":
                self.storage.load(
                    feature_id
                ),
        }