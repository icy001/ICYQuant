"""
Risk decision status.
"""

from enum import Enum


class RiskStatus(Enum):

    APPROVED = "APPROVED"

    REJECTED = "REJECTED"

    REVIEW = "REVIEW"