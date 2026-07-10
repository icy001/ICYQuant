from decimal import Decimal

from services.ledger import (
    LedgerEvent,
    LedgerEventType,
)

from services.projection import (
    PortfolioState,
    CashProjection,
)


def test_cash_deposit():
    state = PortfolioState()

    projection = CashProjection(
        state
    )

    event = LedgerEvent(
        event_type=
            LedgerEventType.CASH_DEPOSITED,
        payload={
            "currency":
                "USD",
            "amount":
                100000
        }
    )

    projection.apply(
        event
    )

    assert (
        state.cash["USD"].balance
        ==
        Decimal("100000")
    )


def test_cash_withdraw():
    state = PortfolioState()

    projection = CashProjection(
        state
    )

    deposit = LedgerEvent(
        event_type=
            LedgerEventType.CASH_DEPOSITED,
        payload={
            "currency":
                "USD",
            "amount":
                100000
        }
    )

    withdraw = LedgerEvent(
        event_type=
            LedgerEventType.CASH_WITHDRAWN,
        payload={
            "currency":
                "USD",
            "amount":
                20000
        }
    )

    projection.apply(
        deposit
    )

    projection.apply(
        withdraw
    )

    assert (
        state.cash["USD"].balance
        ==
        Decimal("80000")
    )