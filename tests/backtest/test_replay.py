from datetime import datetime

from services.backtest import (
    ReplayTick,
    ReplayCursor,
    ReplaySession,
    ReplayFeed,
)


def test_replay_feed():
    session = ReplaySession(
        [
            ReplayTick(
                "AAPL",
                datetime.utcnow(),
                100,
                101,
                99,
                100,
                1000,
            )
        ]
    )

    feed = ReplayFeed(
        session,
        ReplayCursor(),
    )

    tick = feed.next()

    assert tick.symbol == "AAPL"