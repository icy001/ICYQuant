"""
Replication service.
"""


class PortfolioReplicationService:
    def __init__(
        self,
        engine,
    ):
        self.engine = engine

    def replicate(
        self,
        replication_id,
        source,
        target,
    ):
        return self.engine.replicate(replication_id, source, target)