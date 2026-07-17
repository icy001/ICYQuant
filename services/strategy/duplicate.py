"""
Signal duplicate validator.
"""

from __future__ import annotations


class DuplicateSignalValidator:
    def __init__(self):
        self._signals = set()

    async def validate(
        self,
        signal,
    ) -> bool:
        key = (
            signal.strategy_id,
            signal.symbol,
            signal.signal,
        )

        if key in self._signals:
            return False

        self._signals.add(key)
        return True