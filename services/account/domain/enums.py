"""Commit 015 — Account / Position Sync domain vocabulary.

The one thing this module fixes in place is that **Broker Position**,
**Position Ledger** and **Strategy Position** are three different
things (§4).  Nothing here ever conflates them:

* ``AccountStatus``   — lifecycle of the *account sync* itself (§12).
* ``PositionStatus``  — is one broker position internally consistent (§3).
* ``ReconciliationStatus`` / ``ReconciliationOutcome`` — the broker vs
  ledger comparison (§10 / §11).
* ``AccountSyncHealth`` — the Monitoring roll-up (§14).

Time: A-share accounts settle in Asia/Shanghai.  Every timestamp that
enters this module is normalised to ``CST`` so ``sync_latency`` is a
real duration and never a timezone accident (§13).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum

#: Asia/Shanghai (CST, UTC+8) — the trading calendar every A-share
#: account lives in.  Fixed offset is correct for A-shares (no DST).
CST = timezone(timedelta(hours=8))


def now_cst() -> datetime:
    """Timezone-aware "now" in Asia/Shanghai."""
    return datetime.now(CST)


def as_cst(value: datetime) -> datetime:
    """Normalise any datetime to CST; naive values are assumed CST."""
    if value.tzinfo is None:
        return value.replace(tzinfo=CST)
    return value.astimezone(CST)


class AccountStatus(str, Enum):
    """Account sync lifecycle (§12).

    ``CONNECTED → SYNCING → SYNCED`` is the happy path; a snapshot that
    stops arriving goes ``SYNCED → STALE``; a reconciliation failure is
    ``MISMATCH``.  ``ERROR`` / ``OFFLINE`` are the degraded branches.
    """

    CONNECTED = "CONNECTED"
    SYNCING = "SYNCING"
    SYNCED = "SYNCED"
    STALE = "STALE"
    ERROR = "ERROR"
    MISMATCH = "MISMATCH"
    OFFLINE = "OFFLINE"


class SyncSource(str, Enum):
    """Where a snapshot came from — used for traceability (§7)."""

    BROKER = "BROKER"
    SIMULATED = "SIMULATED"
    REPLAY = "REPLAY"


class PositionStatus(str, Enum):
    """Internal consistency of one broker position (§3)."""

    VALID = "VALID"
    INVALID = "INVALID"


class ReconciliationCheck(str, Enum):
    """The five checks §10 demands."""

    ACCOUNT_BALANCE = "ACCOUNT_BALANCE"
    POSITION_QUANTITY = "POSITION_QUANTITY"
    AVAILABLE_QUANTITY = "AVAILABLE_QUANTITY"
    AVERAGE_COST = "AVERAGE_COST"
    MARKET_VALUE = "MARKET_VALUE"


class ReconciliationStatus(str, Enum):
    """Verdict for one position / the whole snapshot (§10).

    The two "missing" statuses are stated from the **broker's** point of
    view:

    * ``MISSING_BROKER`` — the ledger holds a position the broker does
      not report.
    * ``MISSING_LEDGER`` — the broker reports a position the ledger does
      not hold.
    """

    RECONCILED = "RECONCILED"
    MISMATCH = "MISMATCH"
    MISSING_BROKER = "MISSING_BROKER"
    MISSING_LEDGER = "MISSING_LEDGER"
    INVALID = "INVALID"


class ReconciliationOutcome(str, Enum):
    """Overall pass/fail used by the §11 safety rule."""

    PASS = "PASS"
    FAIL = "FAIL"


#: Severity ladder: a mixed report rolls up to the worst member.  Higher
#: wins, so ``INVALID`` > ``MISMATCH`` > ``MISSING_*`` > ``RECONCILED``.
RECONCILIATION_SEVERITY: dict[str, int] = {
    ReconciliationStatus.RECONCILED.value: 0,
    ReconciliationStatus.MISSING_LEDGER.value: 1,
    ReconciliationStatus.MISSING_BROKER.value: 1,
    ReconciliationStatus.MISMATCH.value: 2,
    ReconciliationStatus.INVALID.value: 3,
}


def worst_status(statuses: list[str]) -> str:
    """Roll several statuses up to the most severe one."""
    if not statuses:
        return ReconciliationStatus.RECONCILED.value
    return max(
        statuses,
        key=lambda s: RECONCILIATION_SEVERITY.get(str(s), 0),
    )


class AccountSyncHealth(str, Enum):
    """Monitoring roll-up of account + position sync (§14)."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    OFFLINE = "OFFLINE"


__all__ = [
    "CST",
    "now_cst",
    "as_cst",
    "AccountStatus",
    "SyncSource",
    "PositionStatus",
    "ReconciliationCheck",
    "ReconciliationStatus",
    "ReconciliationOutcome",
    "RECONCILIATION_SEVERITY",
    "worst_status",
    "AccountSyncHealth",
]
