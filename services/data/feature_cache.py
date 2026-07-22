"""
Feature cache.
"""


class FeatureCache:

    def __init__(self):

        self._cache = {}

    def put(
        self,
        key,
        value,
    ):

        self._cache[key] = value

    def get(
        self,
        key,
    ):

        return self._cache.get(
            key,
        )