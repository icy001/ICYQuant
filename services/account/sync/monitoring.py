"""Commit 015 §14 — account / position sync health for Commit 013.

Commit 013 owns alerting; this module only *describes* account sync in
the same language it already uses for market data:

    ACCOUNT SYNC
    ────────────
    Status:       SYNCED
    Last Sync:    15:35:20
    Latency:      180ms

    POSITION
    ────────────
    Positions:    11
    Mismatch:     0

It also surfaces §11's safety rule as ``new_orders_blocked`` — a
reconciliation failure blocks **new Shadow/Live orders** while Paper
Trading (an independent simulated account) is explicitly left running.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from services.account.domain.enums import (
    AccountStatus,
    AccountSyncHealth,
    ReconciliationOutcome,
)

_T = AccountStatus

#: §12 status → §14 health roll-up.
_HEALTH_BY_STATUS: dict[str, str] = {
    _T.OFFLINE.value: AccountSyncHealth.OFFLINE.value,
    _T.ERROR.value: AccountSyncHealth.DEGRADED.value,
    _T.STALE.value: AccountSyncHealth.DEGRADED.value,
    _T.MISMATCH.value: AccountSyncHealth.BLOCKED.value,
    _T.CONNECTED.value: AccountSyncHealth.HEALTHY.value,
    _T.SYNCING.value: AccountSyncHealth.HEALTHY.value,
    _T.SYNCED.value: AccountSyncHealth.HEALTHY.value,
}

#: Statuses in which the broker/ledger truth is not trustworthy, so new
#: Shadow/Live orders must be blocked (§11).  Paper is never in here.
_BLOCKING_STATUSES: frozenset[str] = frozenset(
    {
        _T.MISMATCH.value,
        _T.STALE.value,
        _T.ERROR.value,
        _T.OFFLINE.value,
    }
)


def health_for_status(status: str) -> str:
    """Map a §12 status to a §14 health value."""
    return _HEALTH_BY_STATUS.get(str(status), AccountSyncHealth.DEGRADED.value)


def is_blocking(status: str) -> bool:
    """Whether new Shadow/Live orders are blocked in ``status`` (§11)."""
    return str(status) in _BLOCKING_STATUSES


@dataclass
class AccountSyncHealthSnapshot:
    """§14 health for one account."""

    account_id: str
    status: str
    health: str
    connection_state: Optional[str] = None
    last_successful_sync: Optional[datetime] = None
    last_sync_age_seconds: Optional[float] = None
    sync_latency_ms: Optional[float] = None
    position_count: int = 0
    mismatch_count: int = 0
    invalid_count: int = 0
    reconciliation_status: Optional[str] = None
    reconciliation_outcome: Optional[str] = None
    new_orders_blocked: bool = False

    @property
    def reconciliation_passed(self) -> bool:
        return self.reconciliation_outcome == ReconciliationOutcome.PASS.value

    def as_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "status": self.status,
            "health": self.health,
            "connection_state": self.connection_state,
            "last_successful_sync": (
                self.last_successful_sync.isoformat()
                if self.last_successful_sync
                else None
            ),
            "last_sync_age_seconds": self.last_sync_age_seconds,
            "sync_latency_ms": self.sync_latency_ms,
            "position_count": self.position_count,
            "mismatch_count": self.mismatch_count,
            "invalid_count": self.invalid_count,
            "reconciliation_status": self.reconciliation_status,
            "reconciliation_outcome": self.reconciliation_outcome,
            "new_orders_blocked": self.new_orders_blocked,
        }


class AccountSyncMonitor:
    """Rolls a sync service up into §14 account + position health.

    ``source`` is any object exposing ``status(account_id) -> dict`` and
    ``accounts() -> list`` — in practice
    :class:`~services.account.sync.service.AccountSyncService`.
    """

    def __init__(self, source: Any) -> None:
        self._source = source

    def snapshot(self, account_id: Optional[str] = None) -> AccountSyncHealthSnapshot:
        status = self._source.status(account_id)
        resolved_status = str(status.get("status") or _T.OFFLINE.value)
        return AccountSyncHealthSnapshot(
            account_id=status.get("account_id", account_id or ""),
            status=resolved_status,
            health=health_for_status(resolved_status),
            connection_state=status.get("connection_state"),
            last_successful_sync=_parse_dt(status.get("last_successful_sync")),
            last_sync_age_seconds=status.get("last_sync_age_seconds"),
            sync_latency_ms=status.get("sync_latency_ms"),
            position_count=int(status.get("position_count") or 0),
            mismatch_count=int(status.get("mismatch_count") or 0),
            invalid_count=int(status.get("invalid_count") or 0),
            reconciliation_status=status.get("reconciliation_status"),
            reconciliation_outcome=status.get("reconciliation_outcome"),
            new_orders_blocked=bool(
                status.get("new_orders_blocked", is_blocking(resolved_status))
            ),
        )

    def health(self, account_id: Optional[str] = None) -> dict:
        """§14 health as a plain dict."""
        return self.snapshot(account_id).as_dict()

    def health_report(self) -> dict:
        """Health for every known account, plus an overall roll-up (§14)."""
        accounts = list(self._source.accounts())
        snapshots = [self.snapshot(a.account_id) for a in accounts]
        overall = AccountSyncHealth.HEALTHY.value
        order = {
            AccountSyncHealth.HEALTHY.value: 0,
            AccountSyncHealth.DEGRADED.value: 1,
            AccountSyncHealth.BLOCKED.value: 2,
            AccountSyncHealth.OFFLINE.value: 3,
        }
        if snapshots:
            overall = max(
                (s.health for s in snapshots), key=lambda h: order.get(h, 1)
            )
        return {
            "overall_health": overall,
            "new_orders_blocked": any(s.new_orders_blocked for s in snapshots),
            "account_count": len(snapshots),
            "position_mismatch_count": sum(s.mismatch_count for s in snapshots),
            "accounts": [s.as_dict() for s in snapshots],
        }

    def render(self, account_id: Optional[str] = None) -> str:
        """The §14 text block."""
        snap = self.snapshot(account_id)
        last_sync = (
            snap.last_successful_sync.strftime("%H:%M:%S")
            if snap.last_successful_sync
            else "-"
        )
        latency = (
            f"{snap.sync_latency_ms:.0f}ms"
            if snap.sync_latency_ms is not None
            else "-"
        )
        lines = [
            "ACCOUNT SYNC",
            "────────────",
            f"Status:       {snap.status}",
            f"Health:       {snap.health}",
            f"Last Sync:    {last_sync}",
            f"Latency:      {latency}",
            "",
            "POSITION",
            "────────────",
            f"Positions:    {snap.position_count}",
            f"Mismatch:     {snap.mismatch_count}",
            f"Reconciled:   {'PASS' if snap.reconciliation_passed else 'FAIL'}",
        ]
        if snap.new_orders_blocked:
            lines.append("Orders:       BLOCKED (new Shadow/Live)")
        return "\n".join(lines)


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


__all__ = [
    "AccountSyncHealthSnapshot",
    "AccountSyncMonitor",
    "health_for_status",
    "is_blocking",
]
