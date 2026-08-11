"""OrderPrice value object."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OrderPrice:
    """Order price with optional limit and stop levels."""

    limit_price: float = 0.0
    stop_price: float = 0.0
    average_fill_price: float = 0.0

    @classmethod
    def market(cls) -> OrderPrice:
        return cls()

    @classmethod
    def limit(cls, price: float) -> OrderPrice:
        if price <= 0:
            raise ValueError(f"Limit price must be positive: {price}")
        return cls(limit_price=price)

    @classmethod
    def stop(cls, stop_price: float, limit_price: float = 0.0) -> OrderPrice:
        if stop_price <= 0:
            raise ValueError(f"Stop price must be positive: {stop_price}")
        return cls(limit_price=limit_price, stop_price=stop_price)

    @property
    def has_limit(self) -> bool:
        return self.limit_price > 0

    @property
    def has_stop(self) -> bool:
        return self.stop_price > 0

    def update_fill(self, price: float) -> None:
        """Update average fill price with a new fill."""
        # Simple averaging — real systems use VWAP
        if self.average_fill_price == 0:
            self.average_fill_price = price
        else:
            self.average_fill_price = (self.average_fill_price + price) / 2.0
