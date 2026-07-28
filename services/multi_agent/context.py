"""Shared context manager for multi-agent collaboration."""

from __future__ import annotations


class SharedContextManager:
    """Manages a shared key-value context accessible by all agents.

    Avoids redundant data fetching by allowing agents to read and write
    common context such as market data, user intent, and intermediate
    research results.
    """

    def __init__(self) -> None:
        self.context: dict[str, object] = {}

    def update(self, key: str, value: object) -> None:
        """Store a value in the shared context.

        Args:
            key: Context key.
            value: Value to store.
        """
        self.context[key] = value
