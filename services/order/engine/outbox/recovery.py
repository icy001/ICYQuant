"""Outbox recovery (Commit 33 Part 1.5 #7 / #11)."""

from __future__ import annotations

from .repository import OutboxRepository
from .retry import RetryPolicy


class OutboxRecovery:
    """Re-discovers unfinished events and routes them back to the dispatcher.

    Recovery never re-executes the order and never re-creates events - it only
    confirms the event state, checks the retry policy and puts retryable
    messages back to PENDING so the next ``dispatch_once`` re-processes them:

    .. code-block:: text

        discover unfinished event -> confirm state -> check retry policy
            -> re-enter dispatcher

    A FAILED / PROCESSING message whose retry budget is exhausted stays put.
    """

    def __init__(
        self,
        repository: OutboxRepository,
        retry_policy: RetryPolicy,
    ) -> None:
        self.repository = repository
        self.retry_policy = retry_policy

    def recover(self, limit: int = 100) -> int:
        recovered = 0
        for message in self.repository.unpublished(limit):
            if self.retry_policy.can_retry(message.retry_count):
                self.repository.reset_pending(message.message_id)
                recovered += 1
        return recovered
