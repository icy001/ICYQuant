"""Outbox dispatcher (Commit 33 Part 1.5 #5 / #11)."""

from __future__ import annotations

from typing import List, Protocol, runtime_checkable

from .errors import OutboxPublishError
from .model import OutboxMessage
from .repository import OutboxRepository
from .retry import RetryPolicy


@runtime_checkable
class OutboxPublisher(Protocol):
    """The minimal publish contract the dispatcher needs from the event bus."""

    def publish(self, message: OutboxMessage) -> None: ...


class InMemoryOutboxPublisher:
    """In-memory bus for tests / paper trading.

    ``fail_on_publish`` injects a bus outage; the dispatcher must then mark the
    message FAILED - never pretend it was published (fail-closed, #11).
    """

    def __init__(self) -> None:
        self._published: List[OutboxMessage] = []
        self.fail_on_publish = False

    def publish(self, message: OutboxMessage) -> None:
        if self.fail_on_publish:
            raise OutboxPublishError("event bus unavailable (injected)")
        self._published.append(message)

    @property
    def published_messages(self) -> List[OutboxMessage]:
        return list(self._published)


class OutboxDispatcher:
    """Pulls PENDING messages from the outbox and publishes them.

    A message is marked PROCESSING before the publish attempt and only marked
    PUBLISHED after a successful publish - a crash in between leaves it in
    PROCESSING, where
    :class:`~services.order.engine.outbox.recovery.OutboxRecovery` can pick it
    up again (#11).  The dispatcher never touches the order.
    """

    def __init__(
        self,
        repository: OutboxRepository,
        publisher: OutboxPublisher,
        retry_policy: RetryPolicy,
    ) -> None:
        self.repository = repository
        self.publisher = publisher
        self.retry_policy = retry_policy

    def dispatch_once(self, limit: int = 100) -> int:
        published = 0
        for message in self.repository.pending(limit):
            self.repository.mark_processing(message.message_id)
            try:
                self.publisher.publish(message)
                self.repository.mark_published(message.message_id)
                published += 1
            except Exception as exc:
                self.repository.mark_failed(message.message_id, str(exc))
        return published
