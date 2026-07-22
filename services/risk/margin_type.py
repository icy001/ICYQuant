"""
Margin types.
"""

from enum import Enum


class MarginType(Enum):

    INITIAL = "INITIAL"

    MAINTENANCE = "MAINTENANCE"

    INTRADAY = "INTRADAY"