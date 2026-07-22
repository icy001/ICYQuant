"""
Margin service.
"""


class MarginService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def check(
        self,
        *args,
        **kwargs,
    ):

        return self.engine.check(
            *args,
            **kwargs,
        )