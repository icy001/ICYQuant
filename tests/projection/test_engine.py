from decimal import Decimal

from services.ledger import (
    LedgerEvent,
    LedgerEventType,
)

from services.projection import (
    PortfolioState,
    PositionProjection,
    CashProjection,
    ProjectionEngine,
)


def test_projection_engine_replay():
    state = PortfolioState()

    engine = ProjectionEngine(
        [
            PositionProjection(
                state
            ),
            CashProjection(
                state
            )
        ]
    )

    events = [
        LedgerEvent(
            event_type=
                LedgerEventType.CASH_DEPOSITED,
            payload={
                "currency":
                    "USD",
                "amount":
                    100000
            }
        ),
        LedgerEvent(
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
    ]

    engine.replay(
        events
    )

    assert (
        state.cash["USD"].balance
        ==
        Decimal("100000")
    )

    assert (
        state.positions["NVDA"].quantity
        ==
        Decimal("100")
    )