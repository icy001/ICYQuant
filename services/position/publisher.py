"""
Position event publisher.
"""

from __future__ import annotations

from typing import Awaitable
from typing import Callable
from typing import Optional


Handler = Callable[[object], Optional[Awaitable[None]]]


class PositionEventPublisher:
    def __init__(self):
        self._handlers: list[Handler] = []

    def subscribe(self, handler: Handler):
        self._handlers.append(handler)

    async def publish(self, event):
        for handler in self._handlers:
            result = handler(event)
            if hasattr(result, "__await__"):
                await result