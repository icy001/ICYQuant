class FeatureFlagService:

    def __init__(
        self,
        repository,
        evaluator
    ):
        self.repository = repository
        self.evaluator = evaluator

    def register(self, feature):
        self.repository.save(feature)

    def is_enabled(self, feature_id):
        feature = self.repository.get(feature_id)

        if feature is None:
            return False

        return self.evaluator.enabled(feature)
