"""
Market data schema definitions.
"""

from enum import Enum


class DataType(Enum):
    TICK = "TICK"
    BAR = "BAR"
    ORDER_BOOK = "ORDER_BOOK"
    FUNDAMENTAL = "FUNDAMENTAL"