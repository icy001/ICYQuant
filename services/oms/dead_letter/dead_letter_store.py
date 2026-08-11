"""DeadLetterStore — persistent storage for dead-letter entries."""
from __future__ import annotations

from typing import Dict, List, Optional

from .dead_letter_entry import DeadLetterEntry, DeadLetterStatus


class DeadLetterStore:
    """In-memory dead-letter store.

    Production would use a persistent backend. The store is
    append-only — entries are never deleted, only resolved.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, DeadLetterEntry] = {}
        self._by_message: Dict[str, str] = {}  # message_id → dlq_id
        self._by_order: Dict[str, List[str]] = {}  # order_id → [dlq_ids]

    def add(self, entry: DeadLetterEntry) -> None:
        self._entries[entry.dead_letter_id] = entry
        if entry.message_id:
            self._by_message[entry.message_id] = entry.dead_letter_id
        if entry.order_id not in self._by_order:
            self._by_order[entry.order_id] = []
        self._by_order[entry.order_id].append(entry.dead_letter_id)

    def get(self, dead_letter_id: str) -> Optional[DeadLetterEntry]:
        return self._entries.get(dead_letter_id)

    def get_by_message(self, message_id: str) -> Optional[DeadLetterEntry]:
        dlq_id = self._by_message.get(message_id)
        if dlq_id is None:
            return None
        return self._entries.get(dlq_id)

    def get_by_order(self, order_id: str) -> List[DeadLetterEntry]:
        ids = self._by_order.get(order_id, [])
        return [self._entries[i] for i in ids if i in self._entries]

    def get_open(self) -> List[DeadLetterEntry]:
        return [
            e for e in self._entries.values()
            if e.status in (DeadLetterStatus.OPEN, DeadLetterStatus.RETRYING)
        ]

    def get_all(self) -> List[DeadLetterEntry]:
        return list(self._entries.values())

    @property
    def count(self) -> int:
        return len(self._entries)

    @property
    def open_count(self) -> int:
        return len(self.get_open())
