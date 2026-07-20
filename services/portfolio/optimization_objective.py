"""
Optimization objective.
"""

from enum import Enum


class OptimizationObjective(Enum):
    MAX_RETURN = "MAX_RETURN"
    MIN_RISK = "MIN_RISK"
    MAX_SHARPE = "MAX_SHARPE"