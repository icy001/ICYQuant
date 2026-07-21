"""
Portfolio replication engine.
"""

from datetime import datetime

from .replication import ReplicationRecord


class PortfolioReplicationEngine:
    def __init__(
        self,
        executor,
        repository,
    ):
        self.executor = executor
        self.repository = repository

    def replicate(
        self,
        replication_id,
        source,
        target,
    ):
        self.executor.replicate(source, target)

        record = ReplicationRecord(
            replication_id=replication_id,
            source_node=source,
            target_node=target,
            created_at=datetime.utcnow(),
            status="SUCCESS",
        )

        self.repository.save(record)

        return record