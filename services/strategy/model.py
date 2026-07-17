"""
Strategy aggregate.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import StrategyConfig
from .enums import StrategyStatus


@dataclass
class Strategy:
    config: StrategyConfig
    status: StrategyStatus = StrategyStatus.CREATED