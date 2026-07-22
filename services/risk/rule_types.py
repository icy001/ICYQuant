"""
Built-in risk rule types.
"""

from enum import Enum


class RuleType(Enum):

    POSITION_LIMIT = "POSITION_LIMIT"

    MAX_LOSS = "MAX_LOSS"

    LEVERAGE = "LEVERAGE"

    EXPOSURE = "EXPOSURE"

    MARGIN = "MARGIN"