"""CIO memory for persisting asset allocation and market decisions."""

from __future__ import annotations


class CIOMemory:
    """Persistent memory for the AI CIO.

    Records historical asset allocations, market assessments, decision
    results, and performance to build CIO decision intelligence.
    """

    def __init__(self) -> None:
        self.history: list[dict] = []

    def save(self, decision: dict) -> None:
        """Persist a CIO decision to memory.

        Args:
            decision: The decision dict to save.
        """
        self.history.append(decision)
