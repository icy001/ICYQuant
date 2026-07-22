"""
Risk report types.
"""

from enum import Enum


class RiskReportType(Enum):

    DAILY = "DAILY"

    INTRADAY = "INTRADAY"

    STRESS = "STRESS"

    EXECUTIVE = "EXECUTIVE"