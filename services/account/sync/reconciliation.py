"""Commit 015 §9 / §10 / §11 — broker vs ledger reconciliation.

    Broker Position  →  Normalize  →  Validate  →  Position Snapshot  ─┐
                                                                      ├─► compare
    Position Ledger  ─────────────────────────────────────────────────┘

The five checks §10 names are all produced here:

    ACCOUNT_BALANCE · POSITION_QUANTITY · AVAILABLE_QUANTITY
    AVERAGE_COST    · MARKET_VALUE

and every verdict is one of §10's statuses.  The reconciler **only
reports** — it never touches the broker and never edits the ledger (§9),
and §11's safety rule (mismatch ⇒ block *new shadow/live* orders, while
**leaving Paper Trading untouched**) is exposed as
:attr:`ReconciliationReport.failed` for the service to act on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Iterable, Optional

from services.account.domain.enums import (
    ReconciliationCheck,
    ReconciliationOutcome,
    ReconciliationStatus,
    worst_status,
)
from services.account.domain.snapshot import AccountSnapshot
from services.account.sync.config import AccountSyncConfig
from services.account.sync.ledger import LedgerBalance, LedgerPosition

_ZERO = Decimal("0")


@dataclass(frozen=True)
class ReconciliationItem:
    """One check on one symbol (or the balance) (§10)."""

    symbol: str
    check: str
    broker_value: Optional[Decimal]
    ledger_value: Optional[Decimal]
    status: str

    @property
    def difference(self) -> Optional[Decimal]:
        if self.broker_value is None or self.ledger_value is None:
            return None
        return self.broker_value - self.ledger_value

    @property
    def matched(self) -> bool:
        return self.status == ReconciliationStatus.RECONCILED.value

    def as_dict(self) -> dict:
        def _f(value: Optional[Decimal]) -> Optional[float]:
            return None if value is None else float(value)

        return {
            "symbol": self.symbol,
            "check": self.check,
            "broker_value": _f(self.broker_value),
            "ledger_value": _f(self.ledger_value),
            "difference": _f(self.difference),
            "status": self.status,
        }


@dataclass
class ReconciliationReport:
    """The outcome of reconciling one snapshot against the ledger (§10)."""

    account_id: str
    snapshot_id: str
    timestamp: datetime
    status: str
    outcome: str
    items: list[ReconciliationItem] = field(default_factory=list)

    # ── derived ───────────────────────────────────────────────────────

    @property
    def failed(self) -> bool:
        """§11 — a failure blocks new Shadow/Live orders."""
        return self.outcome == ReconciliationOutcome.FAIL.value

    @property
    def checked(self) -> int:
        return len(self.items)

    def _count(self, status: str) -> int:
        return sum(1 for i in self.items if i.status == status)

    @property
    def matched(self) -> int:
        return self._count(ReconciliationStatus.RECONCILED.value)

    @property
    def mismatch(self) -> int:
        return self._count(ReconciliationStatus.MISMATCH.value)

    @property
    def missing_broker(self) -> int:
        return self._count(ReconciliationStatus.MISSING_BROKER.value)

    @property
    def missing_ledger(self) -> int:
        return self._count(ReconciliationStatus.MISSING_LEDGER.value)

    @property
    def invalid(self) -> int:
        return self._count(ReconciliationStatus.INVALID.value)

    @property
    def mismatch_count(self) -> int:
        """Everything that is not ``RECONCILED`` (§14 monitoring)."""
        return self.checked - self.matched

    def items_for(self, symbol: str) -> list[ReconciliationItem]:
        return [i for i in self.items if i.symbol == symbol]

    def as_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "outcome": self.outcome,
            "checked": self.checked,
            "matched": self.matched,
            "mismatch": self.mismatch,
            "missing_broker": self.missing_broker,
            "missing_ledger": self.missing_ledger,
            "invalid": self.invalid,
            "mismatch_count": self.mismatch_count,
            "items": [i.as_dict() for i in self.items],
        }


class AccountReconciler:
    """Compares a broker snapshot with the Position Ledger (§10)."""

    def __init__(
        self,
        *,
        config: Optional[AccountSyncConfig] = None,
        quantity_tolerance: Decimal = _ZERO,
        available_tolerance: Decimal = _ZERO,
        cost_tolerance: Decimal = Decimal("0.005"),
        value_tolerance: Decimal = Decimal("0.01"),
        balance_tolerance: Decimal = Decimal("0.01"),
    ) -> None:
        self._config = config
        self.quantity_tolerance = Decimal(quantity_tolerance)
        self.available_tolerance = Decimal(available_tolerance)
        self.cost_tolerance = Decimal(cost_tolerance)
        self.value_tolerance = Decimal(value_tolerance)
        self.balance_tolerance = Decimal(balance_tolerance)

    @classmethod
    def from_config(cls, config: AccountSyncConfig) -> "AccountReconciler":
        return cls(config=config)

    # ── comparison ────────────────────────────────────────────────────

    def _compare(
        self,
        symbol: str,
        check: str,
        broker_value: Optional[Decimal],
        ledger_value: Optional[Decimal],
        tolerance: Decimal,
    ) -> ReconciliationItem:
        if broker_value is None or ledger_value is None:
            status = ReconciliationStatus.MISMATCH.value
        elif abs(broker_value - ledger_value) <= tolerance:
            status = ReconciliationStatus.RECONCILED.value
        else:
            status = ReconciliationStatus.MISMATCH.value
        return ReconciliationItem(symbol, check, broker_value, ledger_value, status)

    def _compare_position(
        self,
        broker_position: object,
        ledger_position: LedgerPosition,
    ) -> list[ReconciliationItem]:
        symbol = ledger_position.symbol
        # ``is_valid`` (not ``consistent``): a position whose available /
        # frozen split the broker never sent is INVALID without being
        # arithmetically inconsistent (§3 / §19).
        if not getattr(broker_position, "is_valid", True):
            return [
                ReconciliationItem(
                    symbol,
                    ReconciliationCheck.POSITION_QUANTITY.value,
                    getattr(broker_position, "quantity", None),
                    ledger_position.quantity,
                    ReconciliationStatus.INVALID.value,
                )
            ]
        items = [
            self._compare(
                symbol,
                ReconciliationCheck.POSITION_QUANTITY.value,
                broker_position.quantity,
                ledger_position.quantity,
                self.quantity_tolerance,
            )
        ]
        if ledger_position.available_quantity is not None:
            items.append(
                self._compare(
                    symbol,
                    ReconciliationCheck.AVAILABLE_QUANTITY.value,
                    broker_position.available_quantity,
                    ledger_position.available_quantity,
                    self.available_tolerance,
                )
            )
        if (
            ledger_position.average_cost is not None
            and broker_position.average_cost is not None
        ):
            items.append(
                self._compare(
                    symbol,
                    ReconciliationCheck.AVERAGE_COST.value,
                    broker_position.average_cost,
                    ledger_position.average_cost,
                    self.cost_tolerance,
                )
            )
        if (
            ledger_position.market_value is not None
            and getattr(broker_position, "market_value", None) is not None
        ):
            items.append(
                self._compare(
                    symbol,
                    ReconciliationCheck.MARKET_VALUE.value,
                    broker_position.market_value,
                    ledger_position.market_value,
                    self.value_tolerance,
                )
            )
        return items

    # ── public API ────────────────────────────────────────────────────

    def reconcile(
        self,
        snapshot: AccountSnapshot,
        ledger_positions: Iterable[LedgerPosition],
        ledger_balance: Optional[LedgerBalance] = None,
    ) -> ReconciliationReport:
        """Reconcile ``snapshot`` against the ledger (§10)."""
        broker_map = {p.symbol: p for p in snapshot.positions}
        ledger_map = {l.symbol: l for l in ledger_positions}

        items: list[ReconciliationItem] = []
        for symbol in sorted(set(broker_map) | set(ledger_map)):
            broker_position = broker_map.get(symbol)
            ledger_position = ledger_map.get(symbol)
            if broker_position is None and ledger_position is not None:
                items.append(
                    ReconciliationItem(
                        symbol,
                        ReconciliationCheck.POSITION_QUANTITY.value,
                        None,
                        ledger_position.quantity,
                        ReconciliationStatus.MISSING_BROKER.value,
                    )
                )
                continue
            if ledger_position is None and broker_position is not None:
                items.append(
                    ReconciliationItem(
                        symbol,
                        ReconciliationCheck.POSITION_QUANTITY.value,
                        broker_position.quantity,
                        None,
                        ReconciliationStatus.MISSING_LEDGER.value,
                    )
                )
                continue
            items.extend(
                self._compare_position(broker_position, ledger_position)  # type: ignore[arg-type]
            )

        if ledger_balance is not None and snapshot.balance is not None:
            ledger_total = (
                ledger_balance.total_asset
                if ledger_balance.total_asset is not None
                else ledger_balance.cash
            )
            items.append(
                self._compare(
                    snapshot.account_id,
                    ReconciliationCheck.ACCOUNT_BALANCE.value,
                    snapshot.balance.total_asset,
                    ledger_total,
                    self.balance_tolerance,
                )
            )

        status = worst_status([i.status for i in items])
        outcome = (
            ReconciliationOutcome.PASS.value
            if status == ReconciliationStatus.RECONCILED.value
            else ReconciliationOutcome.FAIL.value
        )
        return ReconciliationReport(
            account_id=snapshot.account_id,
            snapshot_id=snapshot.snapshot_id,
            timestamp=snapshot.timestamp,
            status=status,
            outcome=outcome,
            items=items,
        )


__all__ = ["ReconciliationItem", "ReconciliationReport", "AccountReconciler"]
