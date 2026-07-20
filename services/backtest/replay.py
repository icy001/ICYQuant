"""
Historical market replay.
"""


class MarketReplay:
    async def replay(
        self,
        timeline,
    ):
        for event in timeline:
            yield event