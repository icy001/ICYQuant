"""Fund memory for persisting NAV history, decisions, and risk events."""

from __future__ import annotations


class FundMemory:
    """Persistent memory for institutional fund operations.

    Stores historical NAV, investment decisions, risk events, and
    performance cycles to build institutional fund memory.
    """

    def __init__(self) -> None:
        self.history: list[dict] = []

    def save(self, event: dict) -> None:
        """Persist a fund event to memory.

        Args:
            event: The event dict to save.
        """
        self.history.append(event)
