"""
Reconciliation domain models.

Defines differences between:

External State

and

Internal Projection
"""

from __future__ import annotations


from dataclasses import dataclass


from decimal import Decimal


from enum import Enum


class DifferenceType(str, Enum):
    POSITION_MISMATCH = (
        "POSITION_MISMATCH"
    )

    CASH_MISMATCH = (
        "CASH_MISMATCH"
    )


@dataclass(
    frozen=True,
)
class ReconciliationDifference:
    difference_type: DifferenceType

    symbol: str | None

    expected: Decimal

    actual: Decimal

    delta: Decimal

    message: str