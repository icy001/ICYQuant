from dataclasses import dataclass
from typing import Any, Dict

from services.reconciliation.audit import AuditTrail
from services.reconciliation.comparator import ReconciliationComparator
from services.reconciliation.domain_models import (
    LedgerSnapshot,
    PositionSnapshot,
    ReconciliationResult,
)
from services.reconciliation.replay_engine import ReplayEngine


@dataclass
class RecoveryResult:
    success: bool
    rebuilt_position: float
    reason: str = ""


class ReconciliationEngine:
    def __init__(self) -> None:
        self.comparator = ReconciliationComparator()
        self.replay_engine = ReplayEngine()
        self.audit = AuditTrail()

    def compare(
        self,
        ledger_snapshot: LedgerSnapshot,
        position_snapshot: PositionSnapshot,
    ) -> ReconciliationResult:
        return self.comparator.compare(ledger_snapshot, position_snapshot)

    def recover(
        self,
        result: ReconciliationResult,
        snapshot,
        events,
    ) -> RecoveryResult:
        rebuilt_position = self.replay_engine.rebuild(snapshot, events)

        self.audit.record(
            action="POSITION_REPAIR",
            symbol=result.symbol,
            before=result.position_quantity,
            after=rebuilt_position,
        )

        return RecoveryResult(
            success=True,
            rebuilt_position=rebuilt_position,
            reason="replay_recovery",
        )

    def execute(
        self,
        ledger_snapshot: LedgerSnapshot,
        position_snapshot: PositionSnapshot,
        events: list = None,
    ) -> Dict[str, Any]:
        result = self.compare(ledger_snapshot, position_snapshot)

        if result.status.value == "MISMATCH":
            snapshot = PositionSnapshot(
                symbol=result.symbol,
                quantity=0.0,
            )
            recovery = self.recover(result, snapshot, events or [])

            return {
                "run_id": "v0.2.4-run",
                "status": "RECOVERED" if recovery.success else "FAILED",
                "result": result,
                "recovery": recovery,
                "differences": result.difference,
                "audit_records": len(self.audit.get_records()),
            }

        return {
            "run_id": "v0.2.4-run",
            "status": "HEALTHY",
            "result": result,
            "differences": 0,
            "audit_records": 0,
        }
