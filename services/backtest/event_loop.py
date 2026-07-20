"""
Backtest event loop.
"""


class EventLoop:
    async def run(
        self,
        queue,
        dispatcher,
        handler,
    ):
        while queue._queue:
            event = queue.pop()
            await dispatcher.dispatch(event, handler)