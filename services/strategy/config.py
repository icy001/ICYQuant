"""
Strategy configuration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    symbol: str
    timeframe: str