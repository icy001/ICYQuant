"""
Event-driven backtest engine.
"""

from .event_loop import EventLoop


class BacktestEngine:
    def __init__(
        self,
        loop: EventLoop,
    ):
        self.loop = loop

    async def start(
        self,
        queue,
        dispatcher,
        handler,
    ):
        await self.loop.run(queue, dispatcher, handler)