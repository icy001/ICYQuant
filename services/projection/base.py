"""
Projection interfaces.
"""

from __future__ import annotations


from abc import ABC, abstractmethod


from services.ledger import LedgerEvent


class Projection(ABC):
    """
    Base projection.
    """

    @abstractmethod
    def apply(
        self,
        event: LedgerEvent,
    ) -> None:
        """
        Apply ledger event.
        """

        ...