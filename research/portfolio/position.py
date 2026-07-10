from dataclasses import dataclass


@dataclass
class Position:
    symbol: str
    quantity: float = 0
    average_price: float = 0

    def increase(
        self,
        quantity: float,
        price: float,
    ) -> None:
        total_cost = self.quantity * self.average_price
        new_cost = quantity * price
        
        self.quantity += quantity
        
        if self.quantity != 0:
            self.average_price = (total_cost + new_cost) / self.quantity

    def decrease(
        self,
        quantity: float,
        price: float,
    ) -> None:
        self.quantity -= quantity