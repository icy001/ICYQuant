"""
IncidentContext — structured context carried by an incident.

An incident is never just "position failed": it carries the service, account,
strategy, instrument, venue, component states, and the policy / recovery /
correlation ids that link the incident to the wider control plane
(spec section 9).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class IncidentContext:
    """Contextual snapshot attached to an incident."""

    service: str = ""
    account: str = ""
    strategy: str = ""
    instrument: str = ""
    venue: str = ""

    health_state: str = ""
    risk_state: str = ""
    position_state: str = ""
    ledger_state: str = ""

    policy_id: str = ""
    policy_version: str = ""
    recovery_id: str = ""
    correlation_id: str = ""

    extra: Dict[str, str] = field(default_factory=dict)

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service": self.service,
            "account": self.account,
            "strategy": self.strategy,
            "instrument": self.instrument,
            "venue": self.venue,
            "health_state": self.health_state,
            "risk_state": self.risk_state,
            "position_state": self.position_state,
            "ledger_state": self.ledger_state,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "recovery_id": self.recovery_id,
            "correlation_id": self.correlation_id,
            "extra": dict(self.extra),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncidentContext":
        return cls(
            service=data.get("service", ""),
            account=data.get("account", ""),
            strategy=data.get("strategy", ""),
            instrument=data.get("instrument", ""),
            venue=data.get("venue", ""),
            health_state=data.get("health_state", ""),
            risk_state=data.get("risk_state", ""),
            position_state=data.get("position_state", ""),
            ledger_state=data.get("ledger_state", ""),
            policy_id=data.get("policy_id", ""),
            policy_version=data.get("policy_version", ""),
            recovery_id=data.get("recovery_id", ""),
            correlation_id=data.get("correlation_id", ""),
            extra=dict(data.get("extra", {})),
        )

    # -- helpers ----------------------------------------------------------

    def merge(self, other: "IncidentContext") -> None:
        """Overwrite this context with non-empty fields from `other`."""
        for name, value in vars(other).items():
            if value:
                setattr(self, name, value)

    def bind_policy(self, policy_id: str, policy_version: str = "") -> None:
        self.policy_id = policy_id
        if policy_version:
            self.policy_version = policy_version

    def bind_recovery(self, recovery_id: str) -> None:
        self.recovery_id = recovery_id
