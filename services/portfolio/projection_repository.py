"""
Projection repository.
"""


class ProjectionRepository:

    def __init__(self):

        self.projections = {}

    def save(
        self,
        projection,
    ):

        self.projections[
            projection.portfolio_id
        ] = projection

    def load(
        self,
        portfolio_id,
    ):

        return self.projections.get(
            portfolio_id
        )