"""Alert disposition ledger (Alert Persistence Phase 1).

Integration 015 surfaced Ack/Resolve as UI-session state because the
runtime had no alert store. This module adds the missing piece as a
process-level, append-only disposition ledger keyed by the stable
alert digests emitted by the Alerts Center (``ALT-{sha1(source|message)[:6]}``).

Design follows the platform's in-memory ledger pattern (see
``services/security/audit_center.py``): the store never invents alert
rows — alerts stay *derived* per request from ``runtime.alerts()`` —
it only records operator dispositions against their stable ids:

    TRIGGERED --ack--> ACKNOWLEDGED --resolve--> RESOLVED

Semantics
    * ``resolve`` wins over ``ack`` (terminal state).
    * ``ack`` on a RESOLVED alert is a no-op (resolve stays).
    * Both actions are idempotent: re-ack / re-resolve keep the first
      record (first actor + timestamp is the meaningful one).
    * Alerts are keyed by content digest: if the underlying condition
      changes, the message (and thus the id) changes, and the new
      alert fires as TRIGGERED again — an ack never masks new evidence.
    * Process-level only: a restart resets dispositions to TRIGGERED,
      consistent with the in-memory runtime (pipeline, orders, positions).

Phase 2 (out of scope here): persist to the alerting domain's store /
incident lifecycle, and real notification channels.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

STATUS_TRIGGERED = "TRIGGERED"
STATUS_ACKNOWLEDGED = "ACKNOWLEDGED"
STATUS_RESOLVED = "RESOLVED"

ACTION_ACK = "ACK"
ACTION_RESOLVE = "RESOLVE"


@dataclass(frozen=True)
class DispositionRecord:
    """One operator action against an alert id."""

    alert_id: str
    action: str        # ACTION_ACK | ACTION_RESOLVE
    actor: str         # principal username
    timestamp: str     # ISO-8601 UTC

    def as_dict(self) -> dict:
        return {
            "action": self.action,
            "by": self.actor,
            "at": self.timestamp,
        }


class AlertStateStore:
    """In-memory disposition ledger: alert_id -> latest record.

    Thread-safe: FastAPI serves sync endpoints from a threadpool, so
    concurrent ack/resolve calls must not interleave.
    """

    def __init__(self) -> None:
        self._records: dict[str, DispositionRecord] = {}
        self._lock = threading.Lock()

    # ── write side ──────────────────────────────────────────────
    def ack(self, alert_id: str, actor: str) -> DispositionRecord:
        """TRIGGERED → ACKNOWLEDGED. No-op when already RESOLVED."""
        with self._lock:
            existing = self._records.get(alert_id)
            if existing is not None and existing.action == ACTION_RESOLVE:
                return existing          # resolve is terminal
            if existing is not None:     # already acked — keep first ack
                return existing
            record = DispositionRecord(
                alert_id=alert_id, action=ACTION_ACK, actor=actor,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            self._records[alert_id] = record
            return record

    def resolve(self, alert_id: str, actor: str) -> DispositionRecord:
        """→ RESOLVED (terminal). Overrides an earlier ACK; idempotent."""
        with self._lock:
            existing = self._records.get(alert_id)
            if existing is not None and existing.action == ACTION_RESOLVE:
                return existing          # keep first resolve
            record = DispositionRecord(
                alert_id=alert_id, action=ACTION_RESOLVE, actor=actor,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            self._records[alert_id] = record
            return record

    # ── read side ───────────────────────────────────────────────
    def status_of(self, alert_id: str) -> str:
        """Merged status for a derived alert row."""
        record = self._records.get(alert_id)
        if record is None:
            return STATUS_TRIGGERED
        return STATUS_RESOLVED if record.action == ACTION_RESOLVE \
            else STATUS_ACKNOWLEDGED

    def record_of(self, alert_id: str) -> Optional[DispositionRecord]:
        return self._records.get(alert_id)

    def __len__(self) -> int:
        return len(self._records)

    def reset(self) -> None:
        """Test hook: clear all dispositions."""
        with self._lock:
            self._records.clear()


# Module-level singleton shared by the Alerts API endpoints.
alert_state = AlertStateStore()
