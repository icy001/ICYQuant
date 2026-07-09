from datetime import datetime
from uuid import uuid4

from services.ledger.models.entry import LedgerEntry, LedgerType, LedgerDirection


class LedgerService:
    def __init__(self) -> None:
        self.entries: list[LedgerEntry] = []

    def record(self, entry: LedgerEntry) -> None:
        self.entries.append(entry)

    def record_trade(self, trade_event, user_id: str = "default") -> LedgerEntry:
        cash_change = -trade_event.quantity * trade_event.price if trade_event.side == "BUY" else trade_event.quantity * trade_event.price
        direction = LedgerDirection.DEBIT if trade_event.side == "BUY" else LedgerDirection.CREDIT

        entry = LedgerEntry(
            entry_id=str(uuid4()),
            user_id=user_id,
            event_type="TRADE_FILLED",
            symbol=trade_event.symbol,
            quantity=trade_event.quantity,
            price=trade_event.price,
            cash_change=cash_change,
            ledger_type=LedgerType.TRADE,
            direction=direction,
            amount=abs(cash_change),
            reference_id=trade_event.event_id,
            timestamp=trade_event.timestamp or datetime.utcnow(),
        )

        self.entries.append(entry)
        return entry

    def get_all(self, user_id: str) -> list[LedgerEntry]:
        return [entry for entry in self.entries if entry.user_id == user_id]

    def get_by_symbol(self, symbol: str) -> list[LedgerEntry]:
        return [entry for entry in self.entries if entry.symbol == symbol]

    def get_by_event_type(self, event_type: str) -> list[LedgerEntry]:
        return [entry for entry in self.entries if entry.event_type == event_type]

    def get_balance(self, user_id: str) -> float:
        balance = 0.0
        for entry in self.get_all(user_id):
            if entry.direction == LedgerDirection.CREDIT:
                balance += entry.amount
            else:
                balance -= entry.amount
        return balance