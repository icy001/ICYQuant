"""
In-memory audit store.

Production replacement:

PostgreSQL / Kafka / Immutable storage.
"""

from __future__ import annotations

from .audit import AuditEvent


class AuditStore:
    def __init__(self):
        self.events: list[AuditEvent] = []

    def append(
        self,
        event: AuditEvent,
    ):
        self.events.append(
            event
        )

    def all(
        self,
    ) -> list[AuditEvent]:
        return list(
            self.events
        )

    def count(
        self,
    ) -> int:
        return len(
            self.events
        )