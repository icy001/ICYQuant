"""Alert disposition ledger (Alert Persistence Phase 1).

Integration 015 surfaced Ack/Resolve as UI-session state because the
runtime had no alert store. This module adds the missing piece as a
SQLite-backed, append-only disposition ledger keyed by the stable
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
    * Durable: dispositions are mirrored to a SQLite file so they
      survive process restarts (Phase 1 persistence — see
      ``_persist`` / ``_hydrate``). The in-memory dict stays the live
      cache so object identity is preserved for idempotent re-ack /
      re-resolve within one process.

Phase 2 (out of scope here): incident lifecycle wiring and real
notification channels.
"""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

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
    """SQLite-backed disposition ledger: alert_id -> latest record.

    The in-memory dict is the live cache (preserves object identity for
    idempotent re-ack/re-resolve); SQLite is the durable mirror so
    dispositions survive process restarts. On startup the cache is
    hydrated from the SQLite file.

    Thread-safe: FastAPI serves sync endpoints from a threadpool, so
    concurrent ack/resolve calls must not interleave. ``check_same_thread``
    is disabled and all DB access is serialized under ``self._lock``.
    """

    def __init__(self, db_path: Union[str, Path, None] = None) -> None:
        self._records: dict[str, DispositionRecord] = {}
        self._lock = threading.Lock()
        if db_path is not None:
            path = Path(db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(path), check_same_thread=False)
        else:
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._init_schema()
        self._hydrate()

    def _init_schema(self) -> None:
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS alert_dispositions (
                alert_id   TEXT PRIMARY KEY,
                action     TEXT NOT NULL,
                actor      TEXT NOT NULL,
                timestamp  TEXT NOT NULL
            )"""
        )
        self._conn.commit()

    def _hydrate(self) -> None:
        """Load persisted dispositions into the live cache on startup."""
        rows = self._conn.execute(
            "SELECT alert_id, action, actor, timestamp "
            "FROM alert_dispositions"
        ).fetchall()
        for alert_id, action, actor, timestamp in rows:
            self._records[alert_id] = DispositionRecord(
                alert_id=alert_id, action=action,
                actor=actor, timestamp=timestamp,
            )

    def _persist(self, record: DispositionRecord) -> None:
        """Mirror a new/updated disposition to SQLite (durable)."""
        self._conn.execute(
            "INSERT OR REPLACE INTO alert_dispositions "
            "(alert_id, action, actor, timestamp) VALUES (?, ?, ?, ?)",
            (record.alert_id, record.action, record.actor, record.timestamp),
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the SQLite connection (tests / controlled shutdown)."""
        self._conn.close()

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
            self._persist(record)
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
            self._persist(record)
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
        """Test hook: clear all dispositions (memory + SQLite)."""
        with self._lock:
            self._records.clear()
            self._conn.execute("DELETE FROM alert_dispositions")
            self._conn.commit()


# Module-level singleton shared by the Alerts API endpoints. Persists to
# data/alerts/dispositions.db so dispositions survive process restarts.
_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "alerts" / "dispositions.db"
alert_state = AlertStateStore(db_path=_DB_PATH)
