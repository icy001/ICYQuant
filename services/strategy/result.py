"""
Strategy execution result.
"""

from __future__ import annotations

from dataclasses import dataclass

from .signal import StrategySignal


@dataclass(frozen=True)
class StrategyResult:
    strategy_name: str
    signal: StrategySignal | None