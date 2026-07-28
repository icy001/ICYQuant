class FeatureService:

    def __init__(self, registry):

        self.registry = registry

    def register(self, feature):

        self.registry.register(feature)

    def get(self, name):

        return self.registry.get(name)
