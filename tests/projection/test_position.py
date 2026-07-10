from decimal import Decimal

from services.ledger import (
    LedgerEvent,
    LedgerEventType,
)

from services.projection import (
    PortfolioState,
    PositionProjection,
)


def test_position_projection():
    state = PortfolioState()

    projection = PositionProjection(
        state
    )

    event = LedgerEvent(
        event_type=
            LedgerEventType.ORDER_FILLED,
        payload={
            "symbol":
                "NVDA",
            "quantity":
                100,
            "price":
                150
        }
    )

    projection.apply(
        event
    )

    position = state.positions["NVDA"]

    assert (
        position.quantity
        ==
        Decimal("100")
    )

    assert (
        position.average_price
        ==
        Decimal("150")
    )