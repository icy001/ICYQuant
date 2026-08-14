from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExecutionResult:

    requested_quantity: float

    filled_quantity: float = 0.0

    average_fill_price: float | None = None

    last_fill_price: float | None = None

    @property
    def remaining_quantity(self) -> float:
        return max(
            self.requested_quantity
            - self.filled_quantity,
            0.0,
        )

    @property
    def fully_filled(self) -> bool:
        return (
            self.filled_quantity
            >= self.requested_quantity
        )

    def apply_fill(
        self,
        *,
        quantity: float,
        price: float,
    ) -> None:

        if quantity <= 0:
            raise ValueError(
                "fill quantity must be positive"
            )

        if price <= 0:
            raise ValueError(
                "fill price must be positive"
            )

        if (
            self.filled_quantity + quantity
            > self.requested_quantity
        ):
            raise ValueError(
                "fill quantity exceeds requested quantity"
            )

        previous_value = (
            self.filled_quantity
            * (self.average_fill_price or 0.0)
        )

        new_value = quantity * price

        new_quantity = (
            self.filled_quantity + quantity
        )

        self.average_fill_price = (
            previous_value + new_value
        ) / new_quantity

        self.filled_quantity = new_quantity
        self.last_fill_price = price
