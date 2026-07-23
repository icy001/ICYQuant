"""
Continuous optimization loop.
"""


class ContinuousOptimizationLoop:

    def __init__(
        self,
        adaptation_manager,
    ):

        self.adapter = adaptation_manager

    def optimize(
        self,
        strategy,
        feedback,
    ):

        return self.adapter.adapt(
            strategy,
            feedback,
        )