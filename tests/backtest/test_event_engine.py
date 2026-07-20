import pytest

from services.backtest import (
    BacktestEngine,
    EventDispatcher,
    EventLoop,
    EventProcessor,
    EventQueue,
    BacktestEvent,
)


@pytest.mark.asyncio
async def test_event_engine():
    queue = EventQueue()

    queue.push(object())

    engine = BacktestEngine(EventLoop())

    await engine.start(queue, EventDispatcher(), EventProcessor())

    assert len(queue._queue) == 0


@pytest.mark.asyncio
async def test_event_queue():
    queue = EventQueue()

    event1 = BacktestEvent(event_type="TEST", timestamp="2024-01-01T00:00:00", payload={})
    event2 = BacktestEvent(event_type="TEST", timestamp="2024-01-01T00:00:01", payload={})

    queue.push(event1)
    queue.push(event2)

    assert queue.pop() == event1
    assert queue.pop() == event2


@pytest.mark.asyncio
async def test_event_processor():
    processor = EventProcessor()

    event = BacktestEvent(event_type="TEST", timestamp="2024-01-01T00:00:00", payload={"key": "value"})

    result = await processor.handle(event)

    assert result == event


@pytest.mark.asyncio
async def test_event_dispatcher():
    dispatcher = EventDispatcher()
    processor = EventProcessor()

    event = BacktestEvent(event_type="TEST", timestamp="2024-01-01T00:00:00", payload={})

    result = await dispatcher.dispatch(event, processor)

    assert result == event


def test_backtest_event():
    event = BacktestEvent(
        event_type="MARKET_DATA",
        timestamp="2024-01-01T00:00:00",
        payload={"symbol": "AAPL", "price": 150.0},
    )

    assert event.event_type == "MARKET_DATA"
    assert event.timestamp == "2024-01-01T00:00:00"
    assert event.payload == {"symbol": "AAPL", "price": 150.0}