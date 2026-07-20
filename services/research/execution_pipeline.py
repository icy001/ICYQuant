"""
Research execution pipeline.
"""


class ExecutionPipeline:
    def __init__(
        self,
        market_provider,
        engine_adapter,
    ):
        self.market_provider = market_provider
        self.engine_adapter = engine_adapter

    async def run(
        self,
        context,
    ):
        await self.market_provider.load(context.dataset)
        return await self.engine_adapter.execute(context)