"""
Report types.
"""

from enum import Enum


class ReportType(Enum):
    DAILY = "DAILY"
    RISK = "RISK"
    PERFORMANCE = "PERFORMANCE"
    STRATEGY = "STRATEGY"