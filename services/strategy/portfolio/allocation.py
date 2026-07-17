"""
Strategy capital allocation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Allocation:
    strategy_id: str
    weight: float