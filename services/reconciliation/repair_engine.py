from dataclasses import dataclass
from typing import Dict

from .audit import AuditTrail


@dataclass
class RepairCommand:
    symbol: str
    adjustment: float


class RepairEngine:
    def create_command(
        self,
        reconciliation,
    ) -> RepairCommand:
        return RepairCommand(
            symbol=reconciliation.symbol,
            adjustment=reconciliation.difference,
        )


class RepairWorkflow:
    def __init__(self) -> None:
        self.audit = AuditTrail()

    def repair(
        self,
        reconciliation,
        rebuilt_position: float,
    ) -> Dict:
        result = {
            "symbol": reconciliation.symbol,
            "old": reconciliation.position_quantity,
            "new": rebuilt_position,
            "status": "REPAIRED",
        }

        self.audit.record(
            action="REPAIR",
            symbol=reconciliation.symbol,
            before=reconciliation.position_quantity,
            after=rebuilt_position,
        )

        return result
