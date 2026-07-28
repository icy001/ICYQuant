"""Agent memory for short-term and long-term recall."""

from __future__ import annotations


class AgentMemory:
    """Persistent memory store for an agent's historical records.

    Each agent can save and recall past experiences, decisions, and
    outcomes to improve future task execution.
    """

    def __init__(self) -> None:
        self.records: list[dict] = []

    def save(self, item: dict) -> None:
        """Persist a memory record.

        Args:
            item: The record to store (typically a dict with context).
        """
        self.records.append(item)
