"""
Risk configuration.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskConfiguration:

    max_position_ratio: float

    max_daily_loss: float

    max_leverage: float