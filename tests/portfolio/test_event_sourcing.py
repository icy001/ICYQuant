from datetime import datetime

from services.portfolio import (
    EventReplay,
    PortfolioEvent,
    PortfolioEventSourcingEngine,
    PortfolioEventStore,
)


def test_event_rebuild():
    store = PortfolioEventStore()

    engine = PortfolioEventSourcingEngine(
        store,
        EventReplay(),
    )

    engine.append(
        PortfolioEvent(
            "EVT-001",
            "PORT-001",
            "CASH",
            datetime.utcnow(),
            {"cash": 100000},
        )
    )

    state = engine.rebuild()

    assert state["cash"] == 100000