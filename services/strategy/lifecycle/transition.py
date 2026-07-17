"""
State transition rules.
"""

from .state import StrategyState


class TransitionValidator:
    allowed = {
        StrategyState.CREATED: [
            StrategyState.VALIDATING,
        ],
        StrategyState.VALIDATING: [
            StrategyState.PAPER,
        ],
        StrategyState.PAPER: [
            StrategyState.LIVE,
        ],
        StrategyState.LIVE: [
            StrategyState.DEGRADED,
            StrategyState.SUSPENDED,
        ],
        StrategyState.DEGRADED: [
            StrategyState.SUSPENDED,
            StrategyState.LIVE,
        ],
        StrategyState.SUSPENDED: [
            StrategyState.RETIRED,
        ],
    }

    def can_transition(
        self,
        current,
        target,
    ):
        return target in self.allowed.get(current, [])