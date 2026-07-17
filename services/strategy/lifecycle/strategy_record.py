"""
Strategy registry record.
"""

from __future__ import annotations

from dataclasses import dataclass

from .state import StrategyState


@dataclass
class StrategyRecord:
    strategy_id: str
    version: str
    state: StrategyState
    allocation: float