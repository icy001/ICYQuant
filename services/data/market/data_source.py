"""
Market data source abstraction.
"""

from abc import ABC, abstractmethod


class MarketDataSource(ABC):
    @abstractmethod
    async def fetch(self):
        pass