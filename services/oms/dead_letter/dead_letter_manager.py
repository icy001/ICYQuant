"""DeadLetterManager — manages dead-letter entries lifecycle."""
from __future__ import annotations

from typing import List, Optional

from .dead_letter_entry import DeadLetterEntry, DeadLetterStatus
from .dead_letter_store import DeadLetterStore


class DeadLetterManager:
    """Manages the dead-letter queue.

    Provides:
      - Adding unprocessable messages
      - Retrying entries
      - Resolving entries
      - Escalating entries
      - Ignoring entries (with required actor + reason)
    """

    def __init__(self, store: Optional[DeadLetterStore] = None) -> None:
        self._store = store or DeadLetterStore()

    def add(self, message_id: str, order_id: str,
            message_type: str,
            failure_code: str,
            failure_reason: str,
            payload: Optional[dict] = None) -> DeadLetterEntry:
        """Add a message to the dead-letter queue."""
        # Check for existing entry with same message_id
        existing = self._store.get_by_message(message_id)
        if existing and existing.status not in (
            DeadLetterStatus.RESOLVED, DeadLetterStatus.IGNORED,
        ):
            existing.record_attempt()
            return existing

        entry = DeadLetterEntry.create(
            message_id=message_id,
            order_id=order_id,
            message_type=message_type,
            failure_code=failure_code,
            failure_reason=failure_reason,
            payload=payload,
        )
        self._store.add(entry)
        return entry

    def retry(self, dead_letter_id: str) -> Optional[DeadLetterEntry]:
        """Mark an entry for retry."""
        entry = self._store.get(dead_letter_id)
        if entry is None:
            return None
        entry.record_attempt()
        return entry

    def resolve(self, dead_letter_id: str,
                resolved_by: str,
                reason: str = "") -> Optional[DeadLetterEntry]:
        """Resolve a dead-letter entry."""
        entry = self._store.get(dead_letter_id)
        if entry is None:
            return None
        entry.resolve(resolved_by, reason)
        return entry

    def escalate(self, dead_letter_id: str) -> Optional[DeadLetterEntry]:
        """Escalate a dead-letter entry."""
        entry = self._store.get(dead_letter_id)
        if entry is None:
            return None
        entry.escalate()
        return entry

    def ignore(self, dead_letter_id: str,
               actor: str,
               reason: str) -> Optional[DeadLetterEntry]:
        """Ignore a dead-letter entry — requires actor and reason."""
        if not actor or not reason:
            raise ValueError("Ignoring requires actor and reason")
        entry = self._store.get(dead_letter_id)
        if entry is None:
            return None
        entry.ignore(actor, reason)
        return entry

    def get_open_entries(self) -> List[DeadLetterEntry]:
        return self._store.get_open()

    def get_entries_for_order(self, order_id: str) -> List[DeadLetterEntry]:
        return self._store.get_by_order(order_id)

    @property
    def store(self) -> DeadLetterStore:
        return self._store

    @property
    def open_count(self) -> int:
        return self._store.open_count

    @property
    def total_count(self) -> int:
        return self._store.count
