from decimal import Decimal

from services.ledger import (
    EntrySide,
    Journal,
    TrialBalanceService,
)


def test_trial_balance():
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

    service = TrialBalanceService()

    report = service.verify(
        [journal]
    )

    assert report.balanced
    assert report.debit_total == Decimal("100")
    assert report.credit_total == Decimal("100")