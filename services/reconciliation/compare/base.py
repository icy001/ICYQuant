from abc import ABC, abstractmethod
from typing import Generic, List, TypeVar

from services.reconciliation.models.difference import Difference

T = TypeVar("T")


class Comparator(ABC, Generic[T]):
    """
    Base comparator interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Comparator name."""
        ...

    @abstractmethod
    def compare(
        self,
        internal: List[T],
        external: List[T],
    ) -> List[Difference]:
        """
        Compare internal data with external data.
        """
        ...
