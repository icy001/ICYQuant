from services.contracts.dto import TradeDTO
from services.ledger.models.entry import LedgerDirection, LedgerEntry, LedgerType


class TradeToLedger:
    def convert(self, trade: TradeDTO) -> list[LedgerEntry]:
        cash_entry = LedgerEntry(
            entry_id=f"cash_{trade.trade_id}",
            user_id=trade.user_id,
            ledger_type=LedgerType.CASH,
            direction=LedgerDirection.DEBIT,
            amount=trade.price * trade.quantity,
            reference_id=trade.trade_id,
            timestamp=trade.timestamp,
        )

        position_entry = LedgerEntry(
            entry_id=f"pos_{trade.trade_id}",
            user_id=trade.user_id,
            symbol=trade.symbol,
            ledger_type=LedgerType.POSITION,
            direction=LedgerDirection.CREDIT,
            amount=trade.quantity,
            reference_id=trade.trade_id,
            timestamp=trade.timestamp,
        )

        return [cash_entry, position_entry]
