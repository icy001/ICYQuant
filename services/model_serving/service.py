class ModelServingService:

    def __init__(
        self,
        deployment
    ):

        self.deployment = deployment

    def predict(
        self,
        model_name,
        features
    ):

        model = self.deployment.get(
            model_name
        )

        return model.predict(
            features
        )
