"""
Journal mapper.
"""

from __future__ import annotations

from .journal import Journal
from .model import LedgerEntry
from .orm import (
    JournalModel,
    LedgerEntryModel,
)


class JournalMapper:
    @staticmethod
    def to_model(
        journal: Journal,
    ) -> JournalModel:
        model = JournalModel(
            id=journal.journal_id,
        )

        model.entries = [
            LedgerEntryModel(
                id=entry.entry_id,
                journal_id=journal.journal_id,
                account_code=entry.account_code,
                side=entry.side.value,
                amount=entry.amount,
            )
            for entry in journal.entries
        ]

        return model