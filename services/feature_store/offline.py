class OfflineFeatureStore:

    def __init__(self):

        self.data = []

    def save(self, feature):

        self.data.append(feature)

    def all(self):

        return self.data
