"""
Ledger Domain Events.

Events emitted by the Ledger Aggregate when accounting entries
are created. These are the source of truth for ledger state.

Event types:
- LEDGER_ENTRY_CREATED  — a single accounting entry was created
- LEDGER_BATCH_POSTED    — an atomic batch of entries was posted

All events carry lineage: correlation_id, causation_id, lineage_id.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ------------------------------------------------------------------
#  Event type registry
# ------------------------------------------------------------------

class LedgerEventType:
    LEDGER_ENTRY_CREATED = "LEDGER_ENTRY_CREATED"
    LEDGER_BATCH_POSTED = "LEDGER_BATCH_POSTED"
    LEDGER_ENTRY_CORRECTED = "LEDGER_ENTRY_CORRECTED"


# ------------------------------------------------------------------
#  Base event
# ------------------------------------------------------------------

@dataclass
class LedgerEvent:
    """
    Base class for all Ledger domain events.

    Each event represents an immutable accounting fact.
    """

    event_type: str
    entry_id: str
    account_id: str
    currency: str

    entry_type: str  # TRADE, FEE, COMMISSION, …

    debit: float
    credit: float
    amount: float

    instrument_id: str

    order_id: str
    execution_id: str

    source_event_id: str

    # ── lineage ────────────────────────────────────────────────
    correlation_id: str = ""
    causation_id: str = ""
    lineage_id: str = ""

    # ── metadata ───────────────────────────────────────────────
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    batch_id: str = ""
    version: int = 0

    # ── serialization ──────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "entry_id": self.entry_id,
            "account_id": self.account_id,
            "currency": self.currency,
            "entry_type": self.entry_type,
            "debit": self.debit,
            "credit": self.credit,
            "amount": self.amount,
            "instrument_id": self.instrument_id,
            "order_id": self.order_id,
            "execution_id": self.execution_id,
            "source_event_id": self.source_event_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "lineage_id": self.lineage_id,
            "timestamp": self.timestamp.isoformat(),
            "batch_id": self.batch_id,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LedgerEvent":
        event_type = data.get("event_type", "")
        timestamp_str = data.get("timestamp", "")

        kwargs: Dict[str, Any] = {
            "entry_id": data.get("entry_id", ""),
            "account_id": data.get("account_id", ""),
            "currency": data.get("currency", "USD"),
            "entry_type": data.get("entry_type", ""),
            "debit": float(data.get("debit", 0)),
            "credit": float(data.get("credit", 0)),
            "amount": float(data.get("amount", 0)),
            "instrument_id": data.get("instrument_id", ""),
            "order_id": data.get("order_id", ""),
            "execution_id": data.get("execution_id", ""),
            "source_event_id": data.get("source_event_id", ""),
            "correlation_id": data.get("correlation_id", ""),
            "causation_id": data.get("causation_id", ""),
            "lineage_id": data.get("lineage_id", ""),
            "batch_id": data.get("batch_id", ""),
            "version": int(data.get("version", 0)),
        }

        if timestamp_str:
            kwargs["timestamp"] = datetime.fromisoformat(timestamp_str)

        if event_type == LedgerEventType.LEDGER_BATCH_POSTED:
            kwargs["batch_entry_ids"] = data.get("batch_entry_ids", [])
            kwargs["total_debit"] = float(data.get("total_debit", 0))
            kwargs["total_credit"] = float(data.get("total_credit", 0))
            return LedgerBatchPostedEvent(**kwargs)

        return LedgerEntryCreatedEvent(event_type=event_type, **kwargs)  # type: ignore[arg-type]


# ------------------------------------------------------------------
#  Concrete events
# ------------------------------------------------------------------

class LedgerEntryCreatedEvent(LedgerEvent):
    """Emitted when a single ledger entry is created."""

    def __init__(
        self,
        *,
        entry_id: str,
        account_id: str,
        currency: str,
        entry_type: str,
        debit: float,
        credit: float,
        amount: float,
        instrument_id: str,
        order_id: str,
        execution_id: str,
        source_event_id: str,
        correlation_id: str = "",
        causation_id: str = "",
        lineage_id: str = "",
        timestamp: Optional[datetime] = None,
        batch_id: str = "",
        version: int = 0,
        **_kwargs: object,
    ) -> None:
        super().__init__(
            event_type=LedgerEventType.LEDGER_ENTRY_CREATED,
            entry_id=entry_id,
            account_id=account_id,
            currency=currency,
            entry_type=entry_type,
            debit=debit,
            credit=credit,
            amount=amount,
            instrument_id=instrument_id,
            order_id=order_id,
            execution_id=execution_id,
            source_event_id=source_event_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            lineage_id=lineage_id,
            timestamp=timestamp if timestamp is not None else datetime.now(timezone.utc),
            batch_id=batch_id,
            version=version,
        )


class LedgerBatchPostedEvent(LedgerEvent):
    """Emitted when an atomic batch of ledger entries is posted."""

    def __init__(
        self,
        *,
        entry_id: str,
        account_id: str,
        currency: str,
        entry_type: str,
        debit: float,
        credit: float,
        amount: float,
        instrument_id: str,
        order_id: str,
        execution_id: str,
        source_event_id: str,
        correlation_id: str = "",
        causation_id: str = "",
        lineage_id: str = "",
        timestamp: Optional[datetime] = None,
        batch_id: str = "",
        version: int = 0,
        batch_entry_ids: Optional[List[str]] = None,
        total_debit: float = 0.0,
        total_credit: float = 0.0,
        **_kwargs: object,
    ) -> None:
        super().__init__(
            event_type=LedgerEventType.LEDGER_BATCH_POSTED,
            entry_id=entry_id,
            account_id=account_id,
            currency=currency,
            entry_type=entry_type,
            debit=debit,
            credit=credit,
            amount=amount,
            instrument_id=instrument_id,
            order_id=order_id,
            execution_id=execution_id,
            source_event_id=source_event_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            lineage_id=lineage_id,
            timestamp=timestamp if timestamp is not None else datetime.now(timezone.utc),
            batch_id=batch_id,
            version=version,
        )
        self.batch_entry_ids: List[str] = batch_entry_ids if batch_entry_ids is not None else []
        self.total_debit: float = total_debit
        self.total_credit: float = total_credit

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result["batch_entry_ids"] = self.batch_entry_ids
        result["total_debit"] = self.total_debit
        result["total_credit"] = self.total_credit
        return result
