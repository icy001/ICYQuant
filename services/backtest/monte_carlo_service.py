"""
Monte Carlo service.
"""


class MonteCarloService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine


    def simulate(
        self,
        *args,
        **kwargs,
    ):

        return self.engine.simulate(
            *args,
            **kwargs,
        )