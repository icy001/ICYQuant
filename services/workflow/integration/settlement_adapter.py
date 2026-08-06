"""Settlement Adapter — settlement and clearing integration for workflow-driven post-trade.

Bridges workflow execution with the settlement and clearing system for
post-trade processing including netting, delivery, and clearing.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SettlementStatus(str, Enum):
    PENDING = "PENDING"
    NETTING = "NETTING"
    CLEARING = "CLEARING"
    SETTLED = "SETTLED"
    FAILED = "FAILED"


@dataclass
class SettlementRecord:
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = ""
    order_id: str = ""
    account: str = ""
    symbol: str = ""
    quantity: float = 0.0
    price: float = 0.0
    amount: float = 0.0
    settle_date: Optional[datetime] = None
    status: SettlementStatus = SettlementStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)


class SettlementAdapter:
    """Bridges workflow execution with the settlement system.

    Usage::

        adapter = SettlementAdapter()
        await adapter.start()
        record = await adapter.settle(execution_id="...", account="ACC001", quantity=100)
    """

    def __init__(self) -> None:
        self._lock = __import__("threading").RLock()
        self._started = False
        self._records: Dict[str, SettlementRecord] = {}

    async def start(self) -> None:
        self._started = True
        logger.info("SettlementAdapter: started")

    async def stop(self) -> None:
        self._started = False
        logger.info("SettlementAdapter: stopped")

    async def settle(self, *, execution_id: str, order_id: str, account: str, symbol: str, quantity: float, price: float, metadata: Optional[Dict[str, Any]] = None) -> SettlementRecord:
        amount = quantity * price
        logger.info("SettlementAdapter: settling %s %s %s x%.0f @ %.2f = %.2f", account, symbol, execution_id, quantity, price, amount)
        record = SettlementRecord(
            execution_id=execution_id, order_id=order_id, account=account,
            symbol=symbol, quantity=quantity, price=price, amount=amount,
            status=SettlementStatus.CLEARING, metadata=metadata or {},
        )
        with self._lock:
            self._records[record.record_id] = record
        return record

    async def get_record(self, record_id: str) -> Optional[SettlementRecord]:
        with self._lock:
            return self._records.get(record_id)

    async def list_records(self, *, account: Optional[str] = None) -> List[SettlementRecord]:
        with self._lock:
            results = list(self._records.values())
            if account:
                results = [r for r in results if r.account == account]
            return results

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {"pending_settlements": len(self._records)}
