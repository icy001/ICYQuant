class FeatureRegistry:

    def __init__(self):

        self.features = {}

    def register(self, feature):

        self.features[
            feature.name
        ] = feature

    def get(self, name):

        return self.features.get(name)
