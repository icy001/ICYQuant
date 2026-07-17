"""
Strategy lifecycle states.
"""

from enum import Enum


class StrategyState(Enum):
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    PAPER = "PAPER"
    LIVE = "LIVE"
    DEGRADED = "DEGRADED"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"