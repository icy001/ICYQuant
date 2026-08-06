"""Execution Adapter — bridges the Scheduler with the Execution Management System.

The :class:`ExecutionAdapter` enables scheduled execution operations:
* Algorithmic execution scheduling (TWAP, VWAP, POV)
* Execution monitoring and reporting
* Execution quality analysis
* Smart order routing on schedule

Pipeline::

    Scheduler ──→ ExecutionAdapter ──→ Execution Engine
                      │
            Algo / Monitor / Quality
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExecutionAdapterState(enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class ExecutionAdapter:
    """Adapter for execution management integration.

    Responsibilities:
    * Schedule algorithmic execution jobs
    * Monitor execution progress
    * Generate execution quality reports
    * Route orders through execution algos

    Usage::

        adapter = ExecutionAdapter(execution_engine=engine)
        await adapter.connect()
        await adapter.start_algo("twap_v1", order_spec)
    """

    def __init__(self, execution_engine: Any = None) -> None:
        self._engine = execution_engine
        self._state = ExecutionAdapterState.DISCONNECTED
        self._lock = threading.Lock()
        self._active_algos: Dict[str, Dict[str, Any]] = {}
        self._execution_count: int = 0
        self._completion_count: int = 0

    @property
    def state(self) -> ExecutionAdapterState:
        return self._state

    @property
    def active_algos(self) -> int:
        return len(self._active_algos)

    @property
    def execution_count(self) -> int:
        return self._execution_count

    async def connect(self) -> None:
        self._set_state(ExecutionAdapterState.CONNECTING)
        try:
            if self._engine and hasattr(self._engine, "connect"):
                await self._engine.connect()
            self._set_state(ExecutionAdapterState.CONNECTED)
            logger.info("ExecutionAdapter: connected")
        except Exception as exc:
            self._set_state(ExecutionAdapterState.ERROR)
            raise

    async def disconnect(self) -> None:
        self._active_algos.clear()
        self._set_state(ExecutionAdapterState.DISCONNECTED)

    async def synchronize(self) -> Dict[str, Any]:
        return {"state": self._state.value, "active_algos": len(self._active_algos)}

    # ------------------------------------------------------------------
    # Algo Execution
    # ------------------------------------------------------------------

    async def start_algo(self, algo_id: str, algo_type: str, order_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Start an execution algorithm."""
        self._execution_count += 1
        self._active_algos[algo_id] = {
            "algo_id": algo_id, "type": algo_type, "order_spec": order_spec,
            "started_at": datetime.now(timezone.utc).isoformat(), "status": "running",
        }
        logger.info("ExecutionAdapter: started algo %s (%s)", algo_id, algo_type)
        return {"algo_id": algo_id, "status": "running"}

    async def stop_algo(self, algo_id: str) -> Dict[str, Any]:
        """Stop a running execution algorithm."""
        algo = self._active_algos.pop(algo_id, None)
        if algo:
            self._completion_count += 1
            return {"algo_id": algo_id, "status": "stopped"}
        return {"algo_id": algo_id, "status": "not_found"}

    async def get_execution_status(self, algo_id: str) -> Dict[str, Any]:
        """Get the status of an execution algorithm."""
        algo = self._active_algos.get(algo_id)
        if not algo:
            return {"algo_id": algo_id, "status": "not_found"}
        return {"algo_id": algo_id, "status": algo["status"]}

    async def generate_execution_report(self, report_id: str, algo_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Generate an execution quality report."""
        return {
            "report_id": report_id,
            "algos_analyzed": len(algo_ids) if algo_ids else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _set_state(self, state: ExecutionAdapterState) -> None:
        with self._lock:
            self._state = state
