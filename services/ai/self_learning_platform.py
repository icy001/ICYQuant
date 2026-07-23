"""
Self-learning investment platform.
"""


class SelfLearningPlatform:

    def __init__(
        self,
        evolution_center,
    ):

        self.evolution_center = evolution_center

    def update(
        self,
        experience,
        strategy,
        performance,
    ):

        return self.evolution_center.evolve(
            experience,
            strategy,
            performance,
        )