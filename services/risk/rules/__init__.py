from .exposure_limit import ExposureLimitRule
from .margin_rule import MarginRule
from .max_order_size import MaxOrderSizeRule
from .position_limit import PositionLimitRule


# NOTE: RiskRule is defined in services/risk/rules.py
# (the module file), but the rules/ directory package shadows it.
# Forward-declared here so risk/limits.py can import it.
from abc import ABC, abstractmethod


class RiskRule(ABC):
    """Base rule class — stub. Actual impl in services.risk.rules module."""

    @abstractmethod
    def check(self, order) -> bool:
        ...


__all__ = [
    "MaxOrderSizeRule",
    "PositionLimitRule",
    "ExposureLimitRule",
    "MarginRule",
    "RiskRule",
]