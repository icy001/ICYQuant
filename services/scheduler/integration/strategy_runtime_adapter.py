"""Strategy Runtime Adapter — bridges the Scheduler with the Trading Strategy Runtime.

The :class:`StrategyRuntimeAdapter` enables scheduled execution of
trading strategies:
* Schedule strategy startup/shutdown
* Trigger strategy evaluation cycles
* Route strategy signals through the platform
* Monitor strategy health and performance

Pipeline::

    Scheduler ──→ StrategyRuntimeAdapter ──→ Strategy Engine
                      │                          │
               Schedule / Trigger          Signal → OMS
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class StrategyAdapterState(enum.Enum):
    """Strategy adapter lifecycle states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    ERROR = "error"


class StrategyRuntimeAdapter:
    """Adapter for strategy runtime integration.

    Responsibilities:
    * Schedule strategy lifecycle (start, pause, resume, stop)
    * Trigger strategy evaluation on schedule
    * Collect strategy signals and route to OMS
    * Monitor strategy health metrics

    Usage::

        adapter = StrategyRuntimeAdapter(strategy_engine=engine)
        await adapter.connect()
        await adapter.schedule_strategy("momentum_v1", cron="0 */5 * * *")
    """

    def __init__(self, strategy_engine: Any = None) -> None:
        self._engine = strategy_engine
        self._state = StrategyAdapterState.DISCONNECTED
        self._lock = threading.Lock()
        self._strategies: Dict[str, Dict[str, Any]] = {}
        self._schedule_count: int = 0
        self._signal_count: int = 0

    @property
    def state(self) -> StrategyAdapterState:
        return self._state

    @property
    def strategy_count(self) -> int:
        return len(self._strategies)

    @property
    def schedule_count(self) -> int:
        return self._schedule_count

    @property
    def signal_count(self) -> int:
        return self._signal_count

    async def connect(self) -> None:
        self._set_state(StrategyAdapterState.CONNECTING)
        try:
            if self._engine and hasattr(self._engine, "connect"):
                await self._engine.connect()
            self._set_state(StrategyAdapterState.CONNECTED)
            logger.info("StrategyRuntimeAdapter: connected")
        except Exception as exc:
            self._set_state(StrategyAdapterState.ERROR)
            logger.error("StrategyRuntimeAdapter: connection failed: %s", exc)
            raise

    async def disconnect(self) -> None:
        self._strategies.clear()
        self._set_state(StrategyAdapterState.DISCONNECTED)
        logger.info("StrategyRuntimeAdapter: disconnected")

    async def synchronize(self) -> Dict[str, Any]:
        return {"state": self._state.value, "strategies": len(self._strategies)}

    # ------------------------------------------------------------------
    # Strategy Scheduling
    # ------------------------------------------------------------------

    async def schedule_strategy(
        self, strategy_id: str, cron: Optional[str] = None, parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Schedule a trading strategy for periodic execution."""
        self._schedule_count += 1
        self._strategies[strategy_id] = {
            "strategy_id": strategy_id,
            "cron": cron,
            "parameters": parameters or {},
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
            "status": "scheduled",
        }
        logger.info("StrategyRuntimeAdapter: scheduled %s (cron=%s)", strategy_id, cron)
        return {"strategy_id": strategy_id, "status": "scheduled"}

    async def trigger_evaluation(self, strategy_id: str) -> Dict[str, Any]:
        """Trigger a strategy evaluation cycle."""
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return {"strategy_id": strategy_id, "status": "not_found"}

        result = {"strategy_id": strategy_id, "status": "evaluated", "timestamp": datetime.now(timezone.utc).isoformat()}

        if self._engine and hasattr(self._engine, "evaluate"):
            engine_result = await self._engine.evaluate(strategy_id)
            result["signals"] = getattr(engine_result, "signals", [])
            self._signal_count += len(result.get("signals", []))

        return result

    async def unschedule_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """Remove a strategy from the schedule."""
        self._strategies.pop(strategy_id, None)
        return {"strategy_id": strategy_id, "status": "unscheduled"}

    def _set_state(self, state: StrategyAdapterState) -> None:
        with self._lock:
            self._state = state
