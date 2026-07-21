"""
Projection builder.
"""

from datetime import datetime

from .projection import PortfolioProjection


class ProjectionBuilder:

    def build(
        self,
        portfolio_id,
        state,
    ):

        return PortfolioProjection(
            projection_id=f"PROJ-{portfolio_id}",
            portfolio_id=portfolio_id,
            created_at=datetime.utcnow(),
            data=state,
        )