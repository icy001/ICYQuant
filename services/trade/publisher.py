"""
Trade event publisher.
"""

from __future__ import annotations

from typing import Awaitable
from typing import Callable
from typing import Optional


Handler = Callable[[object], Optional[Awaitable[None]]]


class TradeEventPublisher:
    def __init__(self):
        self._handlers: list[Handler] = []

    def subscribe(self, handler: Handler) -> None:
        self._handlers.append(handler)

    async def publish(self, event: object) -> None:
        for handler in self._handlers:
            result = handler(event)
            if hasattr(result, "__await__"):
                await result