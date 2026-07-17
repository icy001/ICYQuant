"""
Strategy runtime interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .context import StrategyContext


class StrategyRuntime(ABC):
    def __init__(
        self,
        context: StrategyContext,
    ):
        self.context = context

    async def on_start(self):
        pass

    @abstractmethod
    async def on_market(
        self,
        event,
    ):
        """
        Receive market event.
        """

    async def on_stop(self):
        pass