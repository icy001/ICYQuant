"""
Order validation exceptions.
"""

from __future__ import annotations


class OrderValidationError(ValueError):
    """Base validation exception."""


class InvalidQuantity(OrderValidationError):
    """Quantity is invalid."""


class InvalidPrice(OrderValidationError):
    """Price is invalid."""


class InvalidSymbol(OrderValidationError):
    """Symbol is invalid."""


class InvalidOrderType(OrderValidationError):
    """Order type is invalid."""


class OptimisticLockError(RuntimeError):
    """Version conflict."""