"""
Effective Control — merged Portfolio × Strategy control outcome
(Commit 26 Part 1.3).

Portfolio Control cannot be bypassed by Strategy Control: the effective
decision is the AND-combination of both layers, keeping the most restrictive
control active.
"""

from .model import EffectiveStrategyControl
from .resolver import StrategyPortfolioControlResolver

__all__ = [
    "EffectiveStrategyControl",
    "StrategyPortfolioControlResolver",
]
