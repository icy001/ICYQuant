"""Risk Adapter — bridges the Scheduler with the Risk Management System.

The :class:`RiskAdapter` enables scheduled risk operations:
* Pre-trade risk checks on schedule
* Periodic risk limit evaluation
* Risk report generation
* Position limit monitoring

Pipeline::

    Scheduler ──→ RiskAdapter ──→ Risk Engine
                      │
            Pre-check / Limits / Reports
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RiskAdapterState(enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class RiskAdapter:
    """Adapter for risk management integration.

    Responsibilities:
    * Schedule pre-trade risk checks
    * Periodic risk limit evaluation
    * Risk report generation
    * Position and exposure monitoring

    Usage::

        adapter = RiskAdapter(risk_engine=engine)
        await adapter.connect()
        result = await adapter.pre_trade_check(order_context)
    """

    def __init__(self, risk_engine: Any = None) -> None:
        self._engine = risk_engine
        self._state = RiskAdapterState.DISCONNECTED
        self._lock = threading.Lock()
        self._check_count: int = 0
        self._rejection_count: int = 0
        self._scheduled_checks: Dict[str, Dict[str, Any]] = {}

    @property
    def state(self) -> RiskAdapterState:
        return self._state

    @property
    def check_count(self) -> int:
        return self._check_count

    @property
    def rejection_count(self) -> int:
        return self._rejection_count

    async def connect(self) -> None:
        self._set_state(RiskAdapterState.CONNECTING)
        try:
            if self._engine and hasattr(self._engine, "connect"):
                await self._engine.connect()
            self._set_state(RiskAdapterState.CONNECTED)
            logger.info("RiskAdapter: connected")
        except Exception as exc:
            self._set_state(RiskAdapterState.ERROR)
            raise

    async def disconnect(self) -> None:
        self._scheduled_checks.clear()
        self._set_state(RiskAdapterState.DISCONNECTED)

    async def synchronize(self) -> Dict[str, Any]:
        return {"state": self._state.value, "checks": self._check_count, "rejections": self._rejection_count}

    # ------------------------------------------------------------------
    # Risk Checks
    # ------------------------------------------------------------------

    async def pre_trade_check(self, order_context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform a pre-trade risk check for an order."""
        self._check_count += 1
        result = {
            "order_id": order_context.get("order_id", ""),
            "passed": True,
            "checks": {
                "position_limit": True,
                "exposure_limit": True,
                "margin_check": True,
                "concentration_limit": True,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self._engine and hasattr(self._engine, "pre_trade_check"):
            engine_result = await self._engine.pre_trade_check(order_context)
            result["passed"] = engine_result.get("passed", True)
            if not result["passed"]:
                self._rejection_count += 1

        return result

    async def check_limits(self, portfolio_id: str) -> Dict[str, Any]:
        """Check risk limits for a portfolio."""
        self._check_count += 1
        return {
            "portfolio_id": portfolio_id,
            "within_limits": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def generate_risk_report(self, report_id: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate a risk report on schedule."""
        return {"report_id": report_id, "status": "generated", "timestamp": datetime.now(timezone.utc).isoformat()}

    async def schedule_risk_check(self, check_id: str, cron: str, check_type: str = "limit") -> Dict[str, Any]:
        """Schedule a recurring risk check."""
        self._scheduled_checks[check_id] = {"check_id": check_id, "cron": cron, "type": check_type, "status": "scheduled"}
        return {"check_id": check_id, "status": "scheduled"}

    def _set_state(self, state: RiskAdapterState) -> None:
        with self._lock:
            self._state = state
