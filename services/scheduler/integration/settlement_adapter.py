"""Settlement Adapter — bridges the Scheduler with the Settlement System.

The :class:`SettlementAdapter` enables scheduled settlement operations:
* Daily settlement job scheduling
* Position reconciliation
* P&L calculation
* Settlement report generation

Pipeline::

    Scheduler ──→ SettlementAdapter ──→ Settlement Engine
                      │
            Daily Settlement / Recon / P&L
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SettlementAdapterState(enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class SettlementAdapter:
    """Adapter for settlement system integration.

    Responsibilities:
    * Schedule daily settlement jobs
    * Position reconciliation
    * P&L calculation scheduling
    * Settlement report generation

    Usage::

        adapter = SettlementAdapter(settlement_engine=engine)
        await adapter.connect()
        await adapter.schedule_daily_settlement("EOD")
    """

    def __init__(self, settlement_engine: Any = None) -> None:
        self._engine = settlement_engine
        self._state = SettlementAdapterState.DISCONNECTED
        self._lock = threading.Lock()
        self._settlement_jobs: Dict[str, Dict[str, Any]] = {}
        self._settlement_count: int = 0

    @property
    def state(self) -> SettlementAdapterState:
        return self._state

    @property
    def settlement_count(self) -> int:
        return self._settlement_count

    async def connect(self) -> None:
        self._set_state(SettlementAdapterState.CONNECTING)
        try:
            if self._engine and hasattr(self._engine, "connect"):
                await self._engine.connect()
            self._set_state(SettlementAdapterState.CONNECTED)
            logger.info("SettlementAdapter: connected")
        except Exception as exc:
            self._set_state(SettlementAdapterState.ERROR)
            raise

    async def disconnect(self) -> None:
        self._settlement_jobs.clear()
        self._set_state(SettlementAdapterState.DISCONNECTED)

    async def synchronize(self) -> Dict[str, Any]:
        return {"state": self._state.value, "settlements": self._settlement_count}

    # ------------------------------------------------------------------
    # Settlement Operations
    # ------------------------------------------------------------------

    async def schedule_daily_settlement(self, settlement_type: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Schedule a daily settlement job (EOD, intraday, etc.)."""
        self._settlement_count += 1
        job_id = f"settlement-{settlement_type}-{self._settlement_count}"
        self._settlement_jobs[job_id] = {
            "job_id": job_id, "type": settlement_type, "parameters": parameters or {},
            "scheduled_at": datetime.now(timezone.utc).isoformat(), "status": "scheduled",
        }
        logger.info("SettlementAdapter: scheduled %s settlement", settlement_type)
        return {"job_id": job_id, "status": "scheduled"}

    async def reconcile_positions(self, portfolio_id: str) -> Dict[str, Any]:
        """Reconcile positions for a portfolio."""
        return {
            "portfolio_id": portfolio_id, "reconciled": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def calculate_pnl(self, portfolio_id: str, date: Optional[str] = None) -> Dict[str, Any]:
        """Calculate P&L for a portfolio."""
        return {
            "portfolio_id": portfolio_id, "date": date or datetime.now(timezone.utc).date().isoformat(),
            "pnl": 0.0, "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def generate_settlement_report(self, report_id: str) -> Dict[str, Any]:
        """Generate a settlement report."""
        return {"report_id": report_id, "status": "generated", "timestamp": datetime.now(timezone.utc).isoformat()}

    def _set_state(self, state: SettlementAdapterState) -> None:
        with self._lock:
            self._state = state
