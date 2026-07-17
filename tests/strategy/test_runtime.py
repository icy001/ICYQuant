import pytest

from services.strategy import (
    StrategyContext,
    StrategyEngine,
    StrategyRuntime,
)


class DummyStrategy(StrategyRuntime):
    async def on_market(
        self,
        event,
    ):
        return event


@pytest.mark.asyncio
async def test_runtime():
    runtime = DummyStrategy(
        StrategyContext(
            strategy_id="ma",
            account_id="ACC001",
            symbol="AAPL",
        )
    )

    engine = StrategyEngine(runtime)

    await engine.start()

    result = await engine.on_market(123)

    assert result == 123