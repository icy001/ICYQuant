"""
Audit service.
"""


class PortfolioAuditService:

    def __init__(
        self,
        engine,
    ):

        self.engine = engine

    def create(
        self,
        audit_id,
        entity,
        action,
        operator,
        details,
    ):

        return self.engine.log(
            audit_id,
            entity,
            action,
            operator,
            details,
        )