"""
Feedback optimization result.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeedbackResult:
    strategy_id: str
    allocation_factor: float
    reason: str