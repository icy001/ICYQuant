"""
Strategy runtime context.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StrategyContext:
    strategy_id: str
    account_id: str
    symbol: str