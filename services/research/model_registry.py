"""
Model registry.
"""


class ModelRegistry:

    def __init__(self):

        self._models = {}

    def register(
        self,
        model,
    ):

        self._models[
            model.model_id
        ] = model

    def get(
        self,
        model_id,
    ):

        return self._models.get(
            model_id
        )

    def latest(self):

        return list(
            self._models.values()
        )[-1]