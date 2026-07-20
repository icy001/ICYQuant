import pytest

from services.research import (
    ResearchEvent,
    ResearchEventAudit,
    ResearchEventPublisher,
    ResearchEventSubscriber,
    ResearchEventHandler,
    EventService,
)


def test_event_audit():
    audit = ResearchEventAudit()

    event = ResearchEvent(
        event_type="EXPERIMENT_CREATED",
        aggregate_id="exp-001",
        payload={},
    )

    result = audit.record(event)

    assert result["event_type"] == "EXPERIMENT_CREATED"


def test_research_event():
    event = ResearchEvent(
        event_type="BACKTEST_COMPLETED",
        aggregate_id="exp-002",
        payload={"return": 0.12},
    )

    assert event.event_type == "BACKTEST_COMPLETED"
    assert event.aggregate_id == "exp-002"


@pytest.mark.asyncio
async def test_event_publisher():
    publisher = ResearchEventPublisher()

    event = ResearchEvent(
        event_type="OPTIMIZATION_FINISHED",
        aggregate_id="exp-003",
        payload={},
    )

    result = await publisher.publish(event)

    assert result == event


@pytest.mark.asyncio
async def test_event_subscriber():
    subscriber = ResearchEventSubscriber()

    topic = "experiment.created"
    result = await subscriber.subscribe(topic)

    assert result == topic


@pytest.mark.asyncio
async def test_event_handler():
    handler = ResearchEventHandler()

    event = ResearchEvent(
        event_type="REPORT_GENERATED",
        aggregate_id="exp-004",
        payload={},
    )

    result = await handler.handle(event)

    assert result == event


@pytest.mark.asyncio
async def test_event_service():
    publisher = ResearchEventPublisher()
    service = EventService(publisher)

    event = ResearchEvent(
        event_type="ARTIFACT_STORED",
        aggregate_id="exp-005",
        payload={},
    )

    result = await service.emit(event)

    assert result == event