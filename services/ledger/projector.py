from abc import ABC, abstractmethod

from .event import LedgerEvent


class Projection(ABC):
    @abstractmethod
    def apply(self, event: LedgerEvent) -> None:
        pass

    @abstractmethod
    def reset(self) -> None:
        pass