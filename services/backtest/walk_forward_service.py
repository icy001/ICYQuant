"""
Walk-forward service.
"""


class WalkForwardService:

    def __init__(
        self,
        runner,
    ):

        self.runner = runner


    def execute(
        self,
        *args,
        **kwargs,
    ):

        return self.runner.run(
            *args,
            **kwargs,
        )