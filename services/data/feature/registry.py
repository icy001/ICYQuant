"""
Feature registry.
"""


class FeatureRegistry:
    def __init__(self):
        self.features = {}

    def register(
        self,
        definition,
    ):
        self.features[definition.name] = definition

    def get(
        self,
        name,
    ):
        return self.features.get(name)