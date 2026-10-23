"""Account snapshot — one immutable sync observation (§6 / §7).

The snapshot is the *unit of traceability* §7 demands: syncs never
overwrite each other, so "why did the system think I held 10,000 shares
at 15:00?" is answerable from the retained #1001 / #1002 / #1003 chain.

It carries both timestamps (§13): ``timestamp`` is the broker's
observation time, ``received_timestamp`` when ICYQuant pulled it, and
``sync_latency_ms`` their difference.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .balance import AccountBalance
from .enums import AccountStatus, SyncSource
from .position import Position


def _latency_ms(
    broker_timestamp: Optional[datetime],
    received_timestamp: Optional[datetime],
) -> Optional[float]:
    if broker_timestamp is None or received_timestamp is None:
        return None
    delta = received_timestamp - broker_timestamp
    return round(delta.total_seconds() * 1000.0, 3)


@dataclass
class AccountSnapshot:
    """A persisted, traceable account + position observation (§6)."""

    snapshot_id: str
    account_id: str
    timestamp: datetime
    received_timestamp: datetime
    source: str = SyncSource.BROKER.value
    balance: Optional[AccountBalance] = None
    positions: list[Position] = field(default_factory=list)
    status: str = AccountStatus.SYNCING.value
    sequence: int = 0
    reconciliation: Optional[dict] = None

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            raise ValueError("snapshot_id must not be empty")
        if not self.account_id:
            raise ValueError("account_id must not be empty")
        if self.timestamp.tzinfo is None or self.received_timestamp.tzinfo is None:
            raise ValueError(
                "snapshot timestamps must be timezone-aware (§13)"
            )

    # ── derived ───────────────────────────────────────────────────────

    @property
    def sync_latency_ms(self) -> Optional[float]:
        """Broker observation → ICYQuant receipt, in milliseconds (§13)."""
        return _latency_ms(self.timestamp, self.received_timestamp)

    @property
    def position_count(self) -> int:
        return len(self.positions)

    @property
    def symbols(self) -> list[str]:
        return [p.symbol for p in self.positions]

    @property
    def total_market_value(self) -> float:
        return sum(
            (float(p.market_value) for p in self.positions if p.market_value),
            0.0,
        )

    @property
    def invalid_positions(self) -> list[Position]:
        """Positions carrying an INVALID verdict (§3).

        Keyed off :attr:`Position.is_valid`, not ``consistent``: a position
        whose availability the broker never reported has consistent
        arithmetic *by construction* yet is still not trustworthy.
        """
        return [p for p in self.positions if not p.is_valid]

    @property
    def reconciliation_status(self) -> Optional[str]:
        if not self.reconciliation:
            return None
        return self.reconciliation.get("status")

    def as_dict(self, *, include_positions: bool = True) -> dict:
        payload: dict = {
            "snapshot_id": self.snapshot_id,
            "account_id": self.account_id,
            "timestamp": self.timestamp.isoformat(),
            "received_timestamp": self.received_timestamp.isoformat(),
            "sync_latency_ms": self.sync_latency_ms,
            "source": self.source,
            "status": self.status,
            "sequence": self.sequence,
            "position_count": self.position_count,
            "balance": self.balance.as_dict() if self.balance else None,
            "reconciliation": self.reconciliation,
        }
        if include_positions:
            payload["positions"] = [p.as_dict() for p in self.positions]
        return payload


__all__ = ["AccountSnapshot"]
