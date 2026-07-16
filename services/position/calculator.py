"""
Position calculator.
"""

from __future__ import annotations

from decimal import Decimal

from .enums import PositionSide


class PositionCalculator:
    @staticmethod
    def side(quantity: Decimal) -> PositionSide:
        if quantity > 0:
            return PositionSide.LONG
        if quantity < 0:
            return PositionSide.SHORT
        return PositionSide.FLAT