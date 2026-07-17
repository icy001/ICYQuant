"""
Optimization result.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OptimizationResult:
    allocations: list
    expected_sharpe: float
    approved: bool