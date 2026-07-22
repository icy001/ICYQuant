"""
Online / Offline feature pipeline.
"""


class FeaturePipeline:

    def __init__(
        self,
        store,
    ):

        self.store = store

    def publish(
        self,
        entity,
        feature,
        value,
    ):

        self.store.put(
            entity,
            feature,
            value,
        )