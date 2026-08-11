"""QuantityValidator — validates fill quantities against order state."""
from __future__ import annotations

from services.oms.results.command_errors import (
    QuantityExceededError,
    CommandValidationError,
)


class QuantityValidator:
    """Validates that fill quantities don't exceed order limits."""

    @staticmethod
    def validate_fill(order_id: str, command_id: str,
                      fill_quantity: float,
                      remaining_quantity: float,
                      original_quantity: float) -> None:
        """Validate a fill against the order's remaining quantity.

        Raises:
            CommandValidationError: if fill_quantity <= 0
            QuantityExceededError: if fill exceeds remaining
        """
        if fill_quantity <= 0:
            raise CommandValidationError(
                command_id, "INVALID_FILL_QUANTITY",
                f"Fill quantity must be positive, got {fill_quantity}",
                order_id,
            )

        if fill_quantity > remaining_quantity + 0.0001:  # tolerance
            raise QuantityExceededError(
                command_id, order_id,
                requested=fill_quantity,
                available=remaining_quantity,
            )

    @staticmethod
    def validate_parent(order_id: str, command_id: str,
                        child_total: float,
                        parent_quantity: float) -> None:
        """Validate that child orders don't exceed parent quantity."""
        if child_total > parent_quantity + 0.0001:
            raise QuantityExceededError(
                command_id, order_id,
                requested=child_total,
                available=parent_quantity,
            )

    @staticmethod
    def validate_invariant(order_id: str,
                           filled: float,
                           remaining: float,
                           cancelled: float,
                           original: float) -> bool:
        """Check the quantity invariant: filled + remaining + cancelled == original."""
        total = filled + remaining + cancelled
        return abs(total - original) < 0.0001
