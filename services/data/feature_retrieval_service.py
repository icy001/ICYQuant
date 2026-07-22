"""
Feature retrieval service.
"""


class FeatureRetrievalService:

    def __init__(
        self,
        store,
        cache,
    ):

        self.store = store

        self.cache = cache

    def get(
        self,
        entity,
        feature,
    ):

        cache_key = f"{entity}:{feature}"

        value = self.cache.get(
            cache_key,
        )

        if value is not None:

            return value

        value = self.store.get(
            entity,
            feature,
        )

        if value is not None:

            self.cache.put(
                cache_key,
                value,
            )

        return value