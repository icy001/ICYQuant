"""Execution Adapter — trade execution integration for workflow-driven trading.

Bridges workflow execution with the trade execution system, routing orders
to brokers, exchanges, or internal matching engines.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExecStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


@dataclass
class ExecutionReport:
    """Result of a trade execution."""

    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    symbol: str = ""
    side: str = ""
    quantity: float = 0.0
    filled_quantity: float = 0.0
    avg_price: float = 0.0
    status: ExecStatus = ExecStatus.PENDING
    venue: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        return self.status in (ExecStatus.FILLED, ExecStatus.REJECTED, ExecStatus.CANCELLED, ExecStatus.EXPIRED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "avg_price": self.avg_price,
            "status": self.status.value,
            "venue": self.venue,
            "timestamp": self.timestamp.isoformat(),
        }


class ExecutionAdapter:
    """Bridges workflow execution with the trade execution system.

    Usage::

        adapter = ExecutionAdapter()
        await adapter.start()
        report = await adapter.execute(order_id="...", symbol="AAPL", quantity=100)
    """

    def __init__(self) -> None:
        self._lock = __import__("threading").RLock()
        self._started = False
        self._reports: Dict[str, ExecutionReport] = {}
        self._on_fill_callbacks: list = []

    async def start(self) -> None:
        self._started = True
        logger.info("ExecutionAdapter: started")

    async def stop(self) -> None:
        self._started = False
        logger.info("ExecutionAdapter: stopped")

    async def execute(self, *, order_id: str, symbol: str, side: str, quantity: float, venue: str = "AUTO", metadata: Optional[Dict[str, Any]] = None) -> ExecutionReport:
        logger.info("ExecutionAdapter: executing %s %s %s x%.0f", order_id, symbol, side, quantity)
        report = ExecutionReport(
            order_id=order_id, symbol=symbol, side=side, quantity=quantity,
            status=ExecStatus.EXECUTING, venue=venue, metadata=metadata or {},
        )
        with self._lock:
            self._reports[report.execution_id] = report
        return report

    async def get_report(self, execution_id: str) -> Optional[ExecutionReport]:
        with self._lock:
            return self._reports.get(execution_id)

    async def list_reports(self, *, order_id: Optional[str] = None) -> List[ExecutionReport]:
        with self._lock:
            results = list(self._reports.values())
            if order_id:
                results = [r for r in results if r.order_id == order_id]
            return results

    def on_fill(self, callback) -> None:
        self._on_fill_callbacks.append(callback)

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {"active_executions": len(self._reports)}
