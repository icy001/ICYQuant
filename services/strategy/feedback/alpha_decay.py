"""
Alpha decay detector.
"""

from __future__ import annotations


class AlphaDecayDetector:
    def detect(
        self,
        recent_sharpe,
        historical_sharpe,
    ):
        decay = historical_sharpe - recent_sharpe
        return decay