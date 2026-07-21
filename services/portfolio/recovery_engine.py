"""
Portfolio recovery engine.
"""

from datetime import datetime

from .recovery import RecoveryRecord


class PortfolioRecoveryEngine:

    def __init__(
        self,
        validator,
        executor,
        repository,
    ):

        self.validator = validator

        self.executor = executor

        self.repository = repository

    def recover(
        self,
        recovery_id,
        snapshot,
    ):

        if not self.validator.validate(
            snapshot,
        ):

            raise ValueError(
                "Invalid snapshot"
            )

        self.executor.recover(
            snapshot,
        )

        record = RecoveryRecord(
            recovery_id=recovery_id,
            snapshot_id=snapshot.snapshot_id,
            created_at=datetime.utcnow(),
            status="SUCCESS",
        )

        self.repository.save(
            record,
        )

        return record