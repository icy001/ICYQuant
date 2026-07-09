from dataclasses import dataclass


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
