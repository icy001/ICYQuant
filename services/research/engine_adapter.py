"""
Backtest engine adapter.
"""


class BacktestEngineAdapter:
    def __init__(
        self,
        engine,
    ):
        self.engine = engine

    async def execute(
        self,
        context,
    ):
        return await self.engine.run(context)