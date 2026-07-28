"""Research memory for persisting historical reports and analyses."""

from __future__ import annotations


class ResearchMemory:
    """Persistent memory store for institutional research history.

    Saves historical reports, company changes, predictions, and accuracy
    metrics to build an institutional research knowledge base.
    """

    def __init__(self) -> None:
        self.history: list[dict] = []

    def save(self, report: dict) -> None:
        """Persist a research report to memory.

        Args:
            report: The report dict to save.
        """
        self.history.append(report)
