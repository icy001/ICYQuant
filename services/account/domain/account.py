"""Account identity (§2).

The account *registry* — which broker accounts ICYQuant knows about and
their last-seen sync status.  Balances and positions live in
:mod:`.balance` / :mod:`.position`; this is only the header.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .enums import AccountStatus


@dataclass(frozen=True)
class Account:
    """One broker account known to ICYQuant."""

    account_id: str
    name: str = ""
    broker: str = ""
    currency: str = "CNY"
    status: str = AccountStatus.OFFLINE.value
    broker_timestamp: Optional[datetime] = None
    received_timestamp: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.account_id:
            raise ValueError("account_id must not be empty")

    def with_status(self, status: str) -> "Account":
        from dataclasses import replace

        return replace(self, status=str(status))

    def as_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "name": self.name,
            "broker": self.broker,
            "currency": self.currency,
            "status": self.status,
            "broker_timestamp": (
                self.broker_timestamp.isoformat()
                if self.broker_timestamp
                else None
            ),
            "received_timestamp": (
                self.received_timestamp.isoformat()
                if self.received_timestamp
                else None
            ),
        }


__all__ = ["Account"]
