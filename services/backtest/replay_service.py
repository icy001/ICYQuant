"""
Replay service.
"""

from .replay import MarketReplay


class ReplayService:
    def __init__(
        self,
        replay: MarketReplay,
    ):
        self.replay = replay

    async def execute(
        self,
        timeline,
    ):
        async for event in self.replay.replay(timeline.events):
            yield event