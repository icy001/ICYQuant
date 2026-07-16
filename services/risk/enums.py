"""
Risk enums.
"""

from __future__ import annotations

from enum import Enum


class RiskDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REVIEW = "REVIEW"


class RiskType(str, Enum):
    PRE_TRADE = "PRE_TRADE"
    POST_TRADE = "POST_TRADE"