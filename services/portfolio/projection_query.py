"""
Projection query.
"""


class ProjectionQuery:

    def __init__(
        self,
        repository,
    ):

        self.repository = repository

    def get(
        self,
        portfolio_id,
    ):

        return self.repository.load(
            portfolio_id
        )