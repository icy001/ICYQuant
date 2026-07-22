"""
Strategy registration model.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyRegistration:

    strategy_id: str

    strategy_name: str

    version: str