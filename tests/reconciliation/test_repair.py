from decimal import Decimal

from services.reconciliation import (
    RepairService,
    ReconciliationDifference,
    DifferenceType,
)


def test_create_repair_event():
    service = RepairService()

    difference = ReconciliationDifference(
        difference_type=
            DifferenceType.POSITION_MISMATCH,
        symbol="NVDA",
        expected=
            Decimal("100"),
        actual=
            Decimal("80"),
        delta=
            Decimal("-20"),
        message=
            "NVDA mismatch"
    )

    event = service.create_event(
        difference
    )

    assert (
        event.payload["symbol"]
        ==
        "NVDA"
    )

    assert (
        event.payload["adjustment"]
        ==
        "-20"
    )