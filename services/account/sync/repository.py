"""Commit 015 §7 / §8 — snapshot persistence (the System of Record).

Accounts and positions are *trading state*, so their home is PostgreSQL /
the Position Ledger — **not Redis** (§1)::

    account
       ├── account_balance_snapshot
       └── position_snapshot
               └── position_snapshot_item

This module holds the repository *contract* plus an in-memory
implementation.  Two consumers use it:

* tests and the default API singleton (in-memory, deterministic), and
* production, via :class:`~services.account.sync.sql_repository.SqlAccountSnapshotRepository`,
  which reuses the project's existing DB / Repository / Transaction
  stack rather than inventing a new one (§8).

History is retained, never overwritten, so "why did the system think I
held 10,000 shares at 15:00?" is answerable (§7).
"""
from __future__ import annotations

import threading
from typing import Optional, Protocol, runtime_checkable

from services.account.domain.account import Account
from services.account.domain.snapshot import AccountSnapshot


@runtime_checkable
class AccountSnapshotRepository(Protocol):
    """§8 persistence contract."""

    def save_account(self, account: Account) -> None:
        """Upsert the account registry row (§8 ``account``)."""

    def get_account(self, account_id: str) -> Optional[Account]:
        """Fetch one account, or ``None``."""

    def accounts(self) -> list[Account]:
        """Every known account."""

    def save(self, snapshot: AccountSnapshot) -> AccountSnapshot:
        """Append a snapshot, assigning its per-account sequence (§7)."""

    def get(self, snapshot_id: str) -> Optional[AccountSnapshot]:
        """Fetch one snapshot by id."""

    def latest(self, account_id: str) -> Optional[AccountSnapshot]:
        """Most recent snapshot for an account."""

    def history(self, account_id: str, limit: int = 50) -> list[AccountSnapshot]:
        """Most-recent-first snapshot history (§7)."""

    def count(self, account_id: Optional[str] = None) -> int:
        """Snapshot count (per account, or overall)."""

    def clear(self) -> None:
        """Drop everything (test / teardown helper)."""


class InMemoryAccountSnapshotRepository:
    """In-memory :class:`AccountSnapshotRepository` (§8).

    Deterministic and dependency-free, so the sync pipeline is testable
    without a database.  Retains a bounded history per account.
    """

    def __init__(self, *, max_history_per_account: int = 1000) -> None:
        self._max = max(1, max_history_per_account)
        self._accounts: dict[str, Account] = {}
        self._snapshots: dict[str, list[AccountSnapshot]] = {}
        self._by_id: dict[str, AccountSnapshot] = {}
        #: Highest sequence ever issued per account.  Kept *outside* the
        #: retained window on purpose — see :meth:`save`.
        self._last_sequence: dict[str, int] = {}
        self._lock = threading.RLock()

    # ── accounts ──────────────────────────────────────────────────────

    def save_account(self, account: Account) -> None:
        with self._lock:
            self._accounts[account.account_id] = account

    def get_account(self, account_id: str) -> Optional[Account]:
        with self._lock:
            return self._accounts.get(account_id)

    def accounts(self) -> list[Account]:
        with self._lock:
            return [self._accounts[k] for k in sorted(self._accounts)]

    # ── snapshots ─────────────────────────────────────────────────────

    def save(self, snapshot: AccountSnapshot) -> AccountSnapshot:
        with self._lock:
            rows = self._snapshots.setdefault(snapshot.account_id, [])
            if not snapshot.sequence:
                # §7 — a per-account monotonic counter, kept outside the
                # retained window.  Deriving it from ``len(rows)`` restarts
                # the numbering the moment retention prunes a snapshot,
                # minting duplicate sequences and snapshot ids.
                snapshot.sequence = (
                    self._last_sequence.get(snapshot.account_id, 0) + 1
                )
            self._last_sequence[snapshot.account_id] = max(
                self._last_sequence.get(snapshot.account_id, 0), snapshot.sequence
            )
            rows.append(snapshot)
            if len(rows) > self._max:
                evicted = rows[: len(rows) - self._max]
                for old in evicted:
                    self._by_id.pop(old.snapshot_id, None)
                del rows[: len(rows) - self._max]
            self._by_id[snapshot.snapshot_id] = snapshot
            return snapshot

    def get(self, snapshot_id: str) -> Optional[AccountSnapshot]:
        with self._lock:
            return self._by_id.get(snapshot_id)

    def latest(self, account_id: str) -> Optional[AccountSnapshot]:
        with self._lock:
            rows = self._snapshots.get(account_id)
            return rows[-1] if rows else None

    def history(self, account_id: str, limit: int = 50) -> list[AccountSnapshot]:
        with self._lock:
            rows = list(self._snapshots.get(account_id, []))
        if limit is not None and limit >= 0:
            rows = rows[-limit:] if limit else []
        return list(reversed(rows))

    def count(self, account_id: Optional[str] = None) -> int:
        with self._lock:
            if account_id is None:
                return len(self._by_id)
            return len(self._snapshots.get(account_id, []))

    def clear(self) -> None:
        with self._lock:
            self._accounts.clear()
            self._snapshots.clear()
            self._by_id.clear()
            self._last_sequence.clear()


__all__ = [
    "AccountSnapshotRepository",
    "InMemoryAccountSnapshotRepository",
]
