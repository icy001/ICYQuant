"""Ledger Adapter — accounting and ledger integration for workflow-driven post-trade.

Bridges workflow execution with the ledger and accounting system for
position updates, P&L calculation, and reconciliation.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LedgerEntryType(str, Enum):
    TRADE = "TRADE"
    SETTLEMENT = "SETTLEMENT"
    FEE = "FEE"
    DIVIDEND = "DIVIDEND"
    ADJUSTMENT = "ADJUSTMENT"


@dataclass
class LedgerEntry:
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    account: str = ""
    entry_type: LedgerEntryType = LedgerEntryType.TRADE
    symbol: str = ""
    quantity: float = 0.0
    price: float = 0.0
    amount: float = 0.0
    currency: str = "USD"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class LedgerAdapter:
    """Bridges workflow execution with the ledger and accounting system.

    Usage::

        adapter = LedgerAdapter()
        await adapter.start()
        entry = await adapter.record(account="ACC001", entry_type=LedgerEntryType.TRADE, amount=10000)
    """

    def __init__(self) -> None:
        self._lock = __import__("threading").RLock()
        self._started = False
        self._entries: Dict[str, LedgerEntry] = {}
        self._positions: Dict[str, Dict[str, float]] = {}  # account → symbol → quantity

    async def start(self) -> None:
        self._started = True
        logger.info("LedgerAdapter: started")

    async def stop(self) -> None:
        self._started = False
        logger.info("LedgerAdapter: stopped")

    async def record(self, *, account: str, entry_type: LedgerEntryType, symbol: str = "", quantity: float = 0.0, price: float = 0.0, amount: float = 0.0, currency: str = "USD", metadata: Optional[Dict[str, Any]] = None) -> LedgerEntry:
        entry = LedgerEntry(
            account=account, entry_type=entry_type, symbol=symbol,
            quantity=quantity, price=price, amount=amount, currency=currency,
            metadata=metadata or {},
        )
        with self._lock:
            self._entries[entry.entry_id] = entry
            if entry_type == LedgerEntryType.TRADE and symbol:
                if account not in self._positions:
                    self._positions[account] = {}
                self._positions[account][symbol] = self._positions[account].get(symbol, 0.0) + quantity
        logger.debug("LedgerAdapter: recorded entry %s (%s, %s, %.2f)", entry.entry_id, entry_type.value, account, amount)
        return entry

    async def get_position(self, account: str, symbol: str) -> float:
        with self._lock:
            return self._positions.get(account, {}).get(symbol, 0.0)

    async def get_entries(self, *, account: Optional[str] = None, entry_type: Optional[LedgerEntryType] = None, limit: int = 100) -> List[LedgerEntry]:
        with self._lock:
            results = list(self._entries.values())
            if account:
                results = [e for e in results if e.account == account]
            if entry_type:
                results = [e for e in results if e.entry_type == entry_type]
            return results[-limit:]

    async def reconcile(self, account: str) -> Dict[str, Any]:
        with self._lock:
            entries = [e for e in self._entries.values() if e.account == account]
            total_amount = sum(e.amount for e in entries)
            return {
                "account": account,
                "entry_count": len(entries),
                "total_amount": total_amount,
                "positions": self._positions.get(account, {}),
            }

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {"total_entries": len(self._entries), "account_count": len(self._positions)}
