"""
Portfolio event service.
"""


class PortfolioEventService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def append(
        self,
        event,
    ):

        self.engine.append(
            event,
        )

    def rebuild(self):

        return self.engine.rebuild()