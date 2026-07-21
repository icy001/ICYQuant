"""
Portfolio audit engine.
"""


class PortfolioAuditEngine:

    def __init__(
        self,
        recorder,
        repository,
    ):

        self.recorder = recorder

        self.repository = repository

    def log(
        self,
        audit_id,
        entity,
        action,
        operator,
        details,
    ):

        record = self.recorder.record(
            audit_id,
            entity,
            action,
            operator,
            details,
        )

        self.repository.save(
            record
        )

        return record