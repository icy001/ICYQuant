"""
Compliance rule types.
"""

from enum import Enum


class ComplianceType(Enum):
    POSITION_LIMIT = "POSITION_LIMIT"
    EXPOSURE_LIMIT = "EXPOSURE_LIMIT"
    RISK_LIMIT = "RISK_LIMIT"
    ALLOCATION_LIMIT = "ALLOCATION_LIMIT"