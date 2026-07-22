"""
Alpha registry.
"""


class AlphaRegistry:

    def __init__(self):

        self._alphas = {}

    def register(
        self,
        alpha,
    ):

        self._alphas[
            alpha.alpha_id
        ] = alpha

    def get(
        self,
        alpha_id,
    ):

        return self._alphas.get(
            alpha_id
        )

    def list_all(self):

        return list(
            self._alphas.values()
        )