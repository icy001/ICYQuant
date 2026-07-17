"""
Signal confidence.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Confidence:
    score: float

    def valid(self) -> bool:
        return 0.0 <= self.score <= 1.0