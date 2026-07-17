"""
Portfolio domain enums.
"""

from __future__ import annotations

from enum import Enum


class PortfolioStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"