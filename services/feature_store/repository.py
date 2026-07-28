class FeatureRepository:

    def __init__(self):

        self.storage = {}

    def save(self, feature):

        self.storage[
            feature.feature_id
        ] = feature

    def get(self, feature_id):

        return self.storage.get(feature_id)
