"""
Posting engine.
"""

from __future__ import annotations

from decimal import Decimal

from .accounts import LedgerAccounts
from .enums import EntrySide
from .journal import Journal


class PostingEngine:
    def post_trade(
        self,
        trade,
    ) -> Journal:
        journal = Journal()

        amount = trade.quantity * trade.price

        if amount < 0:
            amount = abs(amount)

        journal.add_entry(
            account_code=LedgerAccounts.POSITION,
            side=EntrySide.DEBIT,
            amount=amount,
        )

        journal.add_entry(
            account_code=LedgerAccounts.CASH,
            side=EntrySide.CREDIT,
            amount=amount,
        )

        commission = getattr(
            trade,
            "commission",
            Decimal("0"),
        )

        if commission > 0:
            journal.add_entry(
                account_code=LedgerAccounts.COMMISSION,
                side=EntrySide.DEBIT,
                amount=commission,
            )

            journal.add_entry(
                account_code=LedgerAccounts.CASH,
                side=EntrySide.CREDIT,
                amount=commission,
            )

        if not journal.is_balanced():
            raise ValueError(
                "Journal is not balanced."
            )

        return journal