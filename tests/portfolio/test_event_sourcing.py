from services.portfolio import (
    EventPublisher,
    EventRepository,
    PortfolioEventSourcingEngine,
)


def test_event_sourcing():
    repository = EventRepository()
    publisher = EventPublisher()
    engine = PortfolioEventSourcingEngine(
        repository,
        publisher,
    )

    event = engine.record(
        "EVENT-001",
        "PORTFOLIO_CREATED",
        "PORT-001",
        {"cash": 100000},
    )

    assert event.event_id == "EVENT-001"
    assert event.event_type == "PORTFOLIO_CREATED"
    assert event.portfolio_id == "PORT-001"
    assert len(repository.list_all()) == 1