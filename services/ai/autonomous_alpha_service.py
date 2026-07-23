"""
Autonomous alpha generation service.
"""


class AutonomousAlphaService:

    def __init__(
        self,
        research_loop,
    ):

        self.research_loop = research_loop

    def generate(
        self,
        objective,
    ):

        return self.research_loop.execute(
            objective
        )