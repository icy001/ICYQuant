from services.common.ledger.entry import LedgerDirection, LedgerEntry, LedgerType


class PositionRebuilder:
    def rebuild(self, ledger_entries: list[LedgerEntry]) -> dict[str, float]:
        positions: dict[str, float] = {}

        for entry in ledger_entries:
            if entry.ledger_type != LedgerType.POSITION or not entry.symbol:
                continue

            if entry.symbol not in positions:
                positions[entry.symbol] = 0.0

            if entry.direction == LedgerDirection.CREDIT:
                positions[entry.symbol] += entry.amount
            else:
                positions[entry.symbol] -= entry.amount

        return positions
