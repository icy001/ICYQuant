"""
Portfolio state service.
"""


class PortfolioStateService:

    def __init__(
        self,
        manager,
    ):

        self.manager = manager

    def persist(
        self,
        state,
    ):

        return self.manager.persist(
            state,
        )