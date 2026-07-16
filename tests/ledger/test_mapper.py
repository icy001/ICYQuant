from decimal import Decimal

from services.ledger import (
    EntrySide,
    Journal,
    JournalMapper,
)


def test_journal_mapper():
    journal = Journal()
    journal.add_entry(
        "CASH",
        EntrySide.DEBIT,
        Decimal("100"),
    )
    journal.add_entry(
        "BROKER",
        EntrySide.CREDIT,
        Decimal("100"),
    )

    model = JournalMapper.to_model(journal)

    assert model.id == journal.journal_id
    assert len(model.entries) == 2
    assert model.entries[0].account_code == "CASH"
    assert model.entries[0].side == "DEBIT"