class FeatureRepository:

    def __init__(self):
        self.features = {}

    def save(self, feature):
        self.features[feature.feature_id] = feature

    def get(self, feature_id):
        return self.features.get(feature_id)
