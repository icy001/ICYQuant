"""
Analytics service.
"""


class PortfolioAnalyticsService:
    def __init__(
        self,
        engine,
    ):
        self.engine = engine

    def snapshot(
        self,
        nav_history,
    ):
        return self.engine.generate(nav_history)