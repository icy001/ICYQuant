"""
Strategy Control — per-strategy trading capability gate
(Commit 26 Part 1.3).

Strategy Control decides three capabilities independently:

    Signal Generation
    New Order
    Reduce Order

and supports the risk-reduction path RUNNING → DRAINING → DISABLED.
"""

from .controller import StrategyController
from .decision import StrategyControlDecision
from .policy import StrategyControlPolicy
from .state import StrategyState

__all__ = [
    "StrategyController",
    "StrategyControlDecision",
    "StrategyControlPolicy",
    "StrategyState",
]
