"""
Position limit types.
"""

from enum import Enum


class PositionLimitType(Enum):

    SYMBOL = "SYMBOL"

    ACCOUNT = "ACCOUNT"

    STRATEGY = "STRATEGY"

    PORTFOLIO = "PORTFOLIO"