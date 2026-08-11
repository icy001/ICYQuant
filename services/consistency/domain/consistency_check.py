"""
ConsistencyCheck — the core entity for a single cross-domain consistency
verification run.

Each check captures snapshots from Execution / Position / Ledger and produces a
ConsistencyResult (and optionally reconciliation triggers).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .consistency_status import (
    ConsistencyDomainStatus,
    ReconciliationTriggerPriority,
)


@dataclass
class ExecutionFact:
    """A single confirmed execution fact used as the reference truth."""

    execution_id: str
    order_id: str
    account_id: str
    instrument_id: str
    side: str
    fill_quantity: float
    fill_price: float
    fee: float = 0.0
    commission: float = 0.0
    currency: str = "USD"
    occurred_at: Optional[datetime] = None

    @property
    def trade_value(self) -> float:
        """Trade notional = quantity * price."""
        return self.fill_quantity * self.fill_price

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "order_id": self.order_id,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "side": self.side,
            "fill_quantity": self.fill_quantity,
            "fill_price": self.fill_price,
            "fee": self.fee,
            "commission": self.commission,
            "currency": self.currency,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionFact":
        occurred = data.get("occurred_at")
        return cls(
            execution_id=str(data["execution_id"]),
            order_id=str(data["order_id"]),
            account_id=str(data["account_id"]),
            instrument_id=str(data["instrument_id"]),
            side=str(data["side"]),
            fill_quantity=float(data["fill_quantity"]),
            fill_price=float(data["fill_price"]),
            fee=float(data.get("fee", 0)),
            commission=float(data.get("commission", 0)),
            currency=str(data.get("currency", "USD")),
            occurred_at=datetime.fromisoformat(occurred) if occurred else None,
        )


@dataclass
class PositionView:
    """Snapshot of position state for a given instrument."""

    position_id: str
    account_id: str
    instrument_id: str
    side: str
    quantity: float
    average_price: float = 0.0
    version: int = 0
    last_updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position_id": self.position_id,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "side": self.side,
            "quantity": self.quantity,
            "average_price": self.average_price,
            "version": self.version,
            "last_updated_at": (
                self.last_updated_at.isoformat() if self.last_updated_at else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PositionView":
        updated = data.get("last_updated_at")
        return cls(
            position_id=str(data["position_id"]),
            account_id=str(data["account_id"]),
            instrument_id=str(data["instrument_id"]),
            side=str(data["side"]),
            quantity=float(data["quantity"]),
            average_price=float(data.get("average_price", 0)),
            version=int(data.get("version", 0)),
            last_updated_at=datetime.fromisoformat(updated) if updated else None,
        )


@dataclass
class LedgerView:
    """Snapshot of ledger entries for an execution."""

    account_id: str
    currency: str
    trade_amount: float = 0.0
    fee_amount: float = 0.0
    commission_amount: float = 0.0
    debit_total: float = 0.0
    credit_total: float = 0.0
    balance: float = 0.0
    version: int = 0
    last_updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "currency": self.currency,
            "trade_amount": self.trade_amount,
            "fee_amount": self.fee_amount,
            "commission_amount": self.commission_amount,
            "debit_total": self.debit_total,
            "credit_total": self.credit_total,
            "balance": self.balance,
            "version": self.version,
            "last_updated_at": (
                self.last_updated_at.isoformat() if self.last_updated_at else None
            ),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LedgerView":
        updated = data.get("last_updated_at")
        return cls(
            account_id=str(data["account_id"]),
            currency=str(data.get("currency", "USD")),
            trade_amount=float(data.get("trade_amount", 0)),
            fee_amount=float(data.get("fee_amount", 0)),
            commission_amount=float(data.get("commission_amount", 0)),
            debit_total=float(data.get("debit_total", 0)),
            credit_total=float(data.get("credit_total", 0)),
            balance=float(data.get("balance", 0)),
            version=int(data.get("version", 0)),
            last_updated_at=datetime.fromisoformat(updated) if updated else None,
        )


@dataclass
class ReconciliationTrigger:
    """Generated when a consistency check finds a mismatch."""

    trigger_id: str
    check_id: str
    domain: str  # "POSITION" | "LEDGER"
    failure_type: str
    expected_value: float
    actual_value: float
    delta: float
    priority: ReconciliationTriggerPriority = ReconciliationTriggerPriority.P2
    execution_id: str = ""
    auto_repairable: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "check_id": self.check_id,
            "domain": self.domain,
            "failure_type": self.failure_type,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "delta": self.delta,
            "priority": self.priority.name,
            "execution_id": self.execution_id,
            "auto_repairable": self.auto_repairable,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReconciliationTrigger":
        return cls(
            trigger_id=str(data["trigger_id"]),
            check_id=str(data["check_id"]),
            domain=str(data["domain"]),
            failure_type=str(data["failure_type"]),
            expected_value=float(data["expected_value"]),
            actual_value=float(data["actual_value"]),
            delta=float(data["delta"]),
            priority=ReconciliationTriggerPriority[data.get("priority", "P2")],
            execution_id=str(data.get("execution_id", "")),
            auto_repairable=bool(data.get("auto_repairable", True)),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(timezone.utc),
        )


@dataclass
class ConsistencyCheck:
    """A single cross-domain consistency check with all snapshots."""

    check_id: str
    account_id: str
    instrument_id: str
    check_scope: str = "instrument"  # execution | order | instrument | account
    grace_period_ms: int = 5000  # 5s default

    # Snapshots
    execution_facts: List[ExecutionFact] = field(default_factory=list)
    position_view: Optional[PositionView] = None
    ledger_view: Optional[LedgerView] = None

    # Result
    overall_status: ConsistencyDomainStatus = ConsistencyDomainStatus.DEGRADED
    results: List["ConsistencyResult"] = field(default_factory=list)
    triggers: List[ReconciliationTrigger] = field(default_factory=list)

    correlation_id: str = ""
    lineage_id: str = ""

    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_consistent(self) -> bool:
        return self.overall_status == ConsistencyDomainStatus.CONSISTENT

    @property
    def is_inconsistent(self) -> bool:
        return self.overall_status in (
            ConsistencyDomainStatus.INCONSISTENT,
            ConsistencyDomainStatus.ESCALATED,
        )

    @property
    def has_triggers(self) -> bool:
        return len(self.triggers) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "check_scope": self.check_scope,
            "grace_period_ms": self.grace_period_ms,
            "execution_facts": [f.to_dict() for f in self.execution_facts],
            "position_view": self.position_view.to_dict() if self.position_view else None,
            "ledger_view": self.ledger_view.to_dict() if self.ledger_view else None,
            "overall_status": self.overall_status.value,
            "results": [r.to_dict() for r in self.results],
            "triggers": [t.to_dict() for t in self.triggers],
            "correlation_id": self.correlation_id,
            "lineage_id": self.lineage_id,
            "checked_at": self.checked_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsistencyCheck":
        check = cls(
            check_id=str(data["check_id"]),
            account_id=str(data["account_id"]),
            instrument_id=str(data["instrument_id"]),
            check_scope=str(data.get("check_scope", "instrument")),
            grace_period_ms=int(data.get("grace_period_ms", 5000)),
            execution_facts=[
                ExecutionFact.from_dict(f)
                for f in data.get("execution_facts", [])
            ],
            overall_status=ConsistencyDomainStatus(
                data.get("overall_status", "DEGRADED")
            ),
            results=[],  # populated below
            triggers=[],  # populated below
            correlation_id=str(data.get("correlation_id", "")),
            lineage_id=str(data.get("lineage_id", "")),
            checked_at=datetime.fromisoformat(data["checked_at"])
            if "checked_at" in data
            else datetime.now(timezone.utc),
        )
        # Import here to avoid circular import
        from .consistency_result import ConsistencyResult  # noqa: F811

        check.results = [
            ConsistencyResult.from_dict(r)
            for r in data.get("results", [])
        ]
        check.triggers = [
            ReconciliationTrigger.from_dict(t)
            for t in data.get("triggers", [])
        ]
        if data.get("position_view"):
            check.position_view = PositionView.from_dict(data["position_view"])
        if data.get("ledger_view"):
            check.ledger_view = LedgerView.from_dict(data["ledger_view"])
        return check


# Circular import handled via lazy imports in from_dict
