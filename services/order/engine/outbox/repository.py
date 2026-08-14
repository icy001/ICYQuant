"""Outbox repository (Commit 33 Part 1.5 #3).

The repository only persists event records - it never talks to the event bus.
Responsibility is strictly separated:

.. code-block:: text

    OutboxRepository -> Persistent Event Record -> OutboxDispatcher -> Publisher
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from .errors import (
    DuplicateEventError,
    OutboxMessageNotFoundError,
    OutboxPersistenceError,
)
from .model import OutboxMessage, OutboxStatus


class OutboxRepository(ABC):
    """Persistent event record boundary for the outbox."""

    @abstractmethod
    def append(self, message: OutboxMessage) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, message_id: str) -> Optional[OutboxMessage]:
        raise NotImplementedError

    @abstractmethod
    def pending(self, limit: int = 100) -> Iterable[OutboxMessage]:
        raise NotImplementedError

    @abstractmethod
    def mark_processing(self, message_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def mark_published(self, message_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def mark_failed(self, message_id: str, error: str) -> None:
        raise NotImplementedError

    # Recovery helpers (Commit 33 Part 1.5 #11): after a dispatcher crash or a
    # bus outage the recovery layer must find unfinished messages (PENDING /
    # PROCESSING / FAILED) and put retryable ones back to PENDING.

    @abstractmethod
    def unpublished(self, limit: int = 100) -> Iterable[OutboxMessage]:
        raise NotImplementedError

    @abstractmethod
    def reset_pending(self, message_id: str) -> None:
        raise NotImplementedError


class InMemoryOutboxRepository(OutboxRepository):
    """In-memory outbox store for tests / paper trading.

    ``fail_on_append`` injects a persistence failure so the fail-closed
    behaviour of #10 (order state and outbox live in the same transaction - if
    the outbox cannot be written the command fails) can be verified.
    """

    def __init__(self) -> None:
        self._messages: List[OutboxMessage] = []
        self.fail_on_append = False

    def append(self, message: OutboxMessage) -> None:
        if self.fail_on_append:
            raise OutboxPersistenceError("outbox persistence unavailable (injected)")
        if self.get(message.message_id) is not None or any(
            existing.event_id == message.event_id for existing in self._messages
        ):
            raise DuplicateEventError(message.event_id)
        self._messages.append(message)

    def get(self, message_id: str) -> Optional[OutboxMessage]:
        for message in self._messages:
            if message.message_id == message_id:
                return message
        return None

    def pending(self, limit: int = 100) -> Iterable[OutboxMessage]:
        return self._by_status(OutboxStatus.PENDING, limit)

    def unpublished(self, limit: int = 100) -> Iterable[OutboxMessage]:
        return [
            message
            for message in self._messages
            if message.status is not OutboxStatus.PUBLISHED
        ][:limit]

    def mark_processing(self, message_id: str) -> None:
        self._replace(message_id, status=OutboxStatus.PROCESSING)

    def mark_published(self, message_id: str) -> None:
        self._replace(
            message_id,
            status=OutboxStatus.PUBLISHED,
            published_at=datetime.now(timezone.utc),
        )

    def mark_failed(self, message_id: str, error: str) -> None:
        message = self._require(message_id)
        self._replace(
            message_id,
            status=OutboxStatus.FAILED,
            last_error=error,
            retry_count=message.retry_count + 1,
        )

    def reset_pending(self, message_id: str) -> None:
        self._replace(message_id, status=OutboxStatus.PENDING, last_error=None)

    def _by_status(self, status: OutboxStatus, limit: int) -> Iterable[OutboxMessage]:
        return [message for message in self._messages if message.status is status][:limit]

    def _require(self, message_id: str) -> OutboxMessage:
        message = self.get(message_id)
        if message is None:
            raise OutboxMessageNotFoundError(message_id)
        return message

    def _replace(self, message_id: str, **changes: object) -> None:
        message = self._require(message_id)
        updated = replace(message, **changes)
        self._messages = [
            updated if existing.message_id == message_id else existing
            for existing in self._messages
        ]
