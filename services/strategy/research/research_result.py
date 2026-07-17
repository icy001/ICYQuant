"""
Research evaluation result.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchResult:
    sharpe: float
    max_drawdown: float
    passed: bool