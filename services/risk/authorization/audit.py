"""Authorization audit trail.

An :class:`AuthorizationEvent` is a business fact; an
:class:`AuthorizationAuditRecord` is the durable, immutable audit evidence for
that fact, tagged with the actor that produced it.  The
:class:`AuthorizationAuditTrail` appends records and answers the three trace
queries used by reconciliation and production audit:

* by ``intent_id``
* by ``certificate_id``
* by ``correlation_id``

Records are never modified: re-authorization means appending a new decision /
certificate / event chain, not rewriting history.
"""

from __future__ import annotations

import itertools
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from services.risk.authorization.events import AuthorizationEvent, AuthorizationEventType


@dataclass(frozen=True)
class AuthorizationAuditRecord:
    """Immutable, actor-tagged audit evidence for one authorization event."""

    audit_id: str
    event_id: str
    event_type: AuthorizationEventType

    authorization_id: str
    certificate_id: Optional[str]
    decision_id: str
    intent_id: str

    correlation_id: str

    occurred_at: float

    actor: str

    reason: Optional[str] = None

    sequence: int = 0
    previous_event_id: Optional[str] = None

    def as_dict(self) -> dict:
        """Audit-ready plain mapping of the record."""
        return {
            "audit_id": self.audit_id,
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "authorization_id": self.authorization_id,
            "certificate_id": self.certificate_id,
            "decision_id": self.decision_id,
            "intent_id": self.intent_id,
            "correlation_id": self.correlation_id,
            "occurred_at": self.occurred_at,
            "actor": self.actor,
            "reason": self.reason,
            "sequence": self.sequence,
            "previous_event_id": self.previous_event_id,
        }


_audit_counter = itertools.count(1)


def new_audit_id(timestamp: Optional[float] = None) -> str:
    """Generate a monotonic audit record id.

    Example: ``AUD-20260813-000001``.
    """
    reference = time.time() if timestamp is None else timestamp
    date_part = datetime.fromtimestamp(reference).strftime("%Y%m%d")
    sequence = next(_audit_counter)
    return f"AUD-{date_part}-{sequence:06d}"


def audit_record_from_event(
    event: AuthorizationEvent,
    *,
    actor: str,
    audit_id: Optional[str] = None,
) -> AuthorizationAuditRecord:
    """Turn an authorization event into an immutable audit record."""
    return AuthorizationAuditRecord(
        audit_id=audit_id or new_audit_id(event.occurred_at),
        event_id=event.event_id,
        event_type=event.event_type,
        authorization_id=event.authorization_id,
        certificate_id=event.certificate_id,
        decision_id=event.decision_id,
        intent_id=event.intent_id,
        correlation_id=event.correlation_id,
        occurred_at=event.occurred_at,
        actor=actor,
        reason=event.reason,
        sequence=event.sequence,
        previous_event_id=event.previous_event_id,
    )


def _sort_key(record: AuthorizationAuditRecord):
    return (record.occurred_at, record.sequence)


class AuthorizationAuditRepository(ABC):
    """Domain interface for storing and querying audit records.

    The concrete persistence (database, event bus) is deliberately not bound
    here; this part only fixes the contract.
    """

    @abstractmethod
    def append(self, record: AuthorizationAuditRecord) -> None:
        """Append one audit record (idempotent per audit_id)."""

    @abstractmethod
    def get_by_intent(self, intent_id: str) -> list[AuthorizationAuditRecord]:
        """All records for one intent, in timeline order."""

    @abstractmethod
    def get_by_certificate(self, certificate_id: str) -> list[AuthorizationAuditRecord]:
        """All records touching one certificate, in timeline order."""

    @abstractmethod
    def get_by_correlation(self, correlation_id: str) -> list[AuthorizationAuditRecord]:
        """All records of one correlation chain, in timeline order."""


class InMemoryAuthorizationAuditRepository(AuthorizationAuditRepository):
    """Thread-unsafe in-memory repository (tests / single-process usage)."""

    def __init__(self) -> None:
        self._records: list[AuthorizationAuditRecord] = []
        self._by_audit_id: dict[str, AuthorizationAuditRecord] = {}

    @property
    def records(self) -> list[AuthorizationAuditRecord]:
        """Snapshot of all appended records in append order."""
        return list(self._records)

    def append(self, record: AuthorizationAuditRecord) -> None:
        if record.audit_id in self._by_audit_id:
            return
        self._by_audit_id[record.audit_id] = record
        self._records.append(record)

    def get_by_intent(self, intent_id: str) -> list[AuthorizationAuditRecord]:
        return sorted(
            (r for r in self._records if r.intent_id == intent_id),
            key=_sort_key,
        )

    def get_by_certificate(self, certificate_id: str) -> list[AuthorizationAuditRecord]:
        return sorted(
            (r for r in self._records if r.certificate_id == certificate_id),
            key=_sort_key,
        )

    def get_by_correlation(self, correlation_id: str) -> list[AuthorizationAuditRecord]:
        return sorted(
            (r for r in self._records if r.correlation_id == correlation_id),
            key=_sort_key,
        )


class AuthorizationAuditTrail:
    """Facade that appends events as audit records and answers trace queries.

    The default actor is ``system``; callers can override it per append to
    record e.g. ``risk-engine`` / ``authorization-service`` / ``execution``.
    """

    def __init__(
        self,
        repository: Optional[AuthorizationAuditRepository] = None,
        *,
        actor: str = "system",
    ) -> None:
        self.repository = repository or InMemoryAuthorizationAuditRepository()
        self.actor = actor

    def append(
        self,
        event: AuthorizationEvent,
        *,
        actor: Optional[str] = None,
    ) -> AuthorizationAuditRecord:
        """Record one authorization event as immutable audit evidence."""
        record = audit_record_from_event(event, actor=actor or self.actor)
        self.repository.append(record)
        return record

    def get_by_intent(self, intent_id: str) -> list[AuthorizationAuditRecord]:
        return self.repository.get_by_intent(intent_id)

    def get_by_certificate(self, certificate_id: str) -> list[AuthorizationAuditRecord]:
        return self.repository.get_by_certificate(certificate_id)

    def get_by_correlation(self, correlation_id: str) -> list[AuthorizationAuditRecord]:
        return self.repository.get_by_correlation(correlation_id)
