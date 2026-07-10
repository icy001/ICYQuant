"""
Automatic reconciliation workflow.

Pipeline:

Compare

↓

Repair

↓

Persist Ledger Event
"""

from __future__ import annotations


from services.ledger import (
    LedgerRepository,
)


from services.projection import (
    ProjectionEngine,
)


from .engine import (
    ReconciliationEngine,
)


from .repair_service import (
    RepairService,
)


class ReconciliationWorkflow:
    def __init__(
        self,
        repository: LedgerRepository,
        projection_engine: ProjectionEngine,
    ) -> None:
        self.repository = repository

        self.projection_engine = (
            projection_engine
        )

        self.reconciliation_engine = (
            ReconciliationEngine()
        )

        self.repair_service = (
            RepairService()
        )

    def execute(
        self,
        state,
        external_positions,
    ):
        differences = (
            self.reconciliation_engine
            .reconcile_positions(
                state,
                external_positions
            )
        )

        repair_events = []

        for difference in differences:
            event = (
                self.repair_service
                .create_event(
                    difference
                )
            )

            self.repository.append(
                event
            )

            self.projection_engine.apply(
                event
            )

            repair_events.append(
                event
            )

        return repair_events