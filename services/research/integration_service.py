"""
Backtest integration service.
"""


class IntegrationService:
    def __init__(
        self,
        pipeline,
        collector,
    ):
        self.pipeline = pipeline
        self.collector = collector

    async def execute(
        self,
        context,
    ):
        result = await self.pipeline.run(context)
        return self.collector.collect(result)