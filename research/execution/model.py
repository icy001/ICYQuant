from abc import ABC, abstractmethod


class CostModel(ABC):

    @abstractmethod
    def calculate(self, order, market_price) -> float:
        pass