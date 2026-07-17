"""
Basic risk filter.
"""

from __future__ import annotations


class RiskSignalValidator:
    async def validate(
        self,
        signal,
    ) -> bool:
        return signal.confidence.score >= 0.5