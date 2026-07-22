"""
Market data provider interface.
"""

from abc import ABC, abstractmethod


class DataProvider(ABC):

    @abstractmethod
    def fetch(
        self,
        symbol: str,
    ):

        """Fetch market data."""