"""
Strategy lifecycle manager.
"""

from .state import StrategyState
from .lifecycle_result import LifecycleResult


class StrategyLifecycleManager:
    def __init__(
        self,
        validator,
    ):
        self.validator = validator

    def transition(
        self,
        strategy,
        target,
    ):
        if not self.validator.can_transition(strategy.state, target):
            return LifecycleResult(
                False,
                strategy.state.value,
                "INVALID_TRANSITION",
            )

        strategy.state = target

        return LifecycleResult(
            True,
            target.value,
            "SUCCESS",
        )