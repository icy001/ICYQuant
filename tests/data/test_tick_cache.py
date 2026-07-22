from datetime import datetime

from services.data import (
    Tick,
    TickCache,
)


def test_tick_cache():

    cache = TickCache()

    tick = Tick(
        "AAPL",
        199.9,
        200.1,
        200.0,
        1000,
        datetime.utcnow(),
    )

    cache.update(
        tick
    )

    assert cache.latest(
        "AAPL"
    ).last == 200.0