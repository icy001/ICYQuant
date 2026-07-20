"""
Backtest orchestrator.
"""


class BacktestOrchestrator:
    def __init__(
        self,
        replay,
        engine,
    ):
        self.replay = replay
        self.engine = engine

    async def run(
        self,
        timeline,
    ):
        async for event in self.replay.replay(timeline):
            await self.engine.process(event)