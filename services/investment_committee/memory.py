"""Committee memory for persisting investment meeting records."""

from __future__ import annotations


class CommitteeMemory:
    """Persistent memory for AI Investment Committee meetings.

    Saves meeting records, agent opinions, final decisions, and
    subsequent outcomes to build an AI investment history.
    """

    def __init__(self) -> None:
        self.records: list[dict] = []

    def save(self, meeting: dict) -> None:
        """Persist an investment committee meeting record.

        Args:
            meeting: The meeting dict to save.
        """
        self.records.append(meeting)
