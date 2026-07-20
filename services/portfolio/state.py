"""
Portfolio state.
"""

from enum import Enum


class PortfolioStatus(Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    SUSPENDED = "SUSPENDED"