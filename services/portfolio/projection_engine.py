"""
Projection engine.
"""


class PortfolioProjectionEngine:

    def __init__(
        self,
        repository,
        builder,
    ):

        self.repository = repository

        self.builder = builder

    def project(
        self,
        portfolio_id,
        state,
    ):

        projection = self.builder.build(
            portfolio_id,
            state,
        )

        self.repository.save(
            projection,
        )

        return projection