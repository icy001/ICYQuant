from decimal import Decimal

from services.ledger import (
    EntrySide,
    Journal,
)


def test_balanced_journal():
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

    assert journal.is_balanced()