"""OrderQuantity value object with invariants."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OrderQuantity:
    """Tracks the quantity lifecycle of an order.

    Invariant:
        filled + remaining + cancelled == original
    """

    original: float = 0.0
    filled: float = 0.0
    remaining: float = 0.0
    cancelled: float = 0.0

    @classmethod
    def for_original(cls, quantity: float) -> OrderQuantity:
        qty = cls(
            original=quantity,
            remaining=quantity,
        )
        qty._validate()
        return qty

    def fill(self, amount: float) -> OrderQuantity:
        """Apply a fill of `amount` shares."""
        if amount <= 0:
            raise ValueError("Fill amount must be positive")
        if amount > self.remaining:
            raise ValueError(
                f"Fill {amount} exceeds remaining {self.remaining}"
            )
        self.filled += amount
        self.remaining -= amount
        self._validate()
        return self

    def cancel_remaining(self, amount: float = 0) -> OrderQuantity:
        """Cancel remaining quantity."""
        qty = amount if amount > 0 else self.remaining
        if qty > self.remaining:
            raise ValueError(
                f"Cancel {qty} exceeds remaining {self.remaining}"
            )
        self.cancelled += qty
        self.remaining -= qty
        self._validate()
        return self

    @property
    def is_full(self) -> bool:
        return self.remaining <= 0 and self.filled >= self.original

    @property
    def fill_pct(self) -> float:
        return (self.filled / self.original * 100.0) if self.original else 0.0

    def _validate(self) -> None:
        total = self.filled + self.remaining + self.cancelled
        if abs(total - self.original) > 0.0001:
            raise OrderQuantityError(
                f"Quantity invariant violated: "
                f"filled={self.filled} + remaining={self.remaining} "
                f"+ cancelled={self.cancelled} = {total}, "
                f"expected {self.original}",
                filled=self.filled,
                remaining=self.remaining,
                cancelled=self.cancelled,
                original=self.original,
            )


class OrderQuantityError(ValueError):
    def __init__(self, message: str, filled: float = 0, remaining: float = 0,
                 cancelled: float = 0, original: float = 0) -> None:
        super().__init__(message)
        self.filled = filled
        self.remaining = remaining
        self.cancelled = cancelled
        self.original = original
