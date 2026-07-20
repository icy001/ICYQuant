import pytest

from services.backtest import (
    MarketReplay,
    ReplayCursor,
    ReplayClock,
    PlaybackController,
    ReplayTimeline,
    ReplayService,
)


@pytest.mark.asyncio
async def test_market_replay():
    replay = MarketReplay()

    events = []

    async for event in replay.replay([1, 2, 3]):
        events.append(event)

    assert events == [1, 2, 3]


def test_replay_cursor():
    cursor = ReplayCursor()

    assert cursor.position == 0

    cursor.advance()

    assert cursor.position == 1


def test_replay_clock():
    clock = ReplayClock()

    now = clock.now()

    assert now is not None


def test_playback_controller():
    controller = PlaybackController()

    assert controller.speed == 1.0

    controller2 = PlaybackController(speed=2.0)

    assert controller2.speed == 2.0


def test_replay_timeline():
    timeline = ReplayTimeline(events=[1, 2, 3])

    assert len(timeline.events) == 3


@pytest.mark.asyncio
async def test_replay_service():
    replay = MarketReplay()
    service = ReplayService(replay)

    timeline = ReplayTimeline(events=[10, 20, 30])

    events = []

    async for event in service.execute(timeline):
        events.append(event)

    assert events == [10, 20, 30]