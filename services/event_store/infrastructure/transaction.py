"""Event store transaction boundary (Commit 34 Part 1.2 #6).

An ``EventStoreTransaction`` makes a multi-event stream append atomic:

.. code-block:: text

    BEGIN
      validate version
      validate event sequence
      append v8 / v9 / v10
    COMMIT
        or
    ROLLBACK            # nothing is left behind

Events are either all persisted or none are - a stream can never be left with
a hole (v8, v9, missing v10).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple

from services.event_store.domain.event import StoredEvent


class EventStoreTransaction(ABC):
    """Transaction interface for an atomic stream append (#6)."""

    @abstractmethod
    def append_stream(
        self,
        aggregate_id: str,
        expected_version: int,
        events: Tuple[StoredEvent, ...],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def commit(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def rollback(self) -> None:
        raise NotImplementedError
