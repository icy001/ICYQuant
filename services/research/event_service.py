"""
Research event service.
"""

from .publisher import ResearchEventPublisher


class EventService:
    def __init__(
        self,
        publisher,
    ):
        self.publisher = publisher

    async def emit(
        self,
        event,
    ):
        return await self.publisher.publish(event)