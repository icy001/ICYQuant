"""
AI feature engineering agent.
"""


class FeatureEngineeringAgent:

    def __init__(
        self,
        feature_store,
        ai_service,
    ):

        self.feature_store = feature_store

        self.ai_service = ai_service

    def generate(
        self,
        dataset,
    ):

        prompt = f"""
        Generate quantitative features.

        Dataset:

        {dataset}

        """

        return self.ai_service.execute(
            prompt
        )