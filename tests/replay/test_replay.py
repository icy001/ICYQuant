from decimal import Decimal

from services.ledger import (
    LedgerEvent,
    LedgerEventType,
)

from services.projection import (
    PortfolioState,
    ProjectionEngine,
    PositionProjection,
    CashProjection,
)

from services.replay import (
    ReplayEngine,
)


def test_replay_rebuild_state():
    state = PortfolioState()

    projection_engine = ProjectionEngine(
        [
            PositionProjection(
                state
            ),
            CashProjection(
                state
            )
        ]
    )

    replay = ReplayEngine(
        projection_engine,
        state
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

    result = replay.rebuild(
        events
    )

    assert (
        result.positions["NVDA"]
        .quantity
        ==
        Decimal("100")
    )