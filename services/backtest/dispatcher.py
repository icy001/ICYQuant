"""
Event dispatcher.
"""


class EventDispatcher:
    async def dispatch(
        self,
        event,
        handler,
    ):
        return await handler.handle(event)