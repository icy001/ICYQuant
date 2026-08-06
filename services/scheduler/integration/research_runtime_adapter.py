"""Research Runtime Adapter — bridges the Scheduler with the Research Platform.

The :class:`ResearchRuntimeAdapter` enables scheduled research operations:
* Factor research and computation jobs
* Backtest execution scheduling
* Portfolio analysis and optimization
* Research report generation

Pipeline::

    Scheduler ──→ ResearchRuntimeAdapter ──→ Research Platform
                      │                           │
               Factor / Backtest           Analysis / Report
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ResearchAdapterState(enum.Enum):
    """Research adapter lifecycle states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    ERROR = "error"


class ResearchRuntimeAdapter:
    """Adapter for research platform integration.

    Responsibilities:
    * Schedule factor computation jobs
    * Schedule backtest runs
    * Schedule portfolio analysis
    * Schedule research report generation
    * Chain research pipelines (factor → backtest → analysis → report)

    Usage::

        adapter = ResearchRuntimeAdapter(research_platform=platform)
        await adapter.connect()
        await adapter.schedule_factor_research("momentum_factors", cron="0 6 * * 1-5")
        await adapter.schedule_backtest("strategy_v2", cron="0 8 * * 1")
    """

    def __init__(self, research_platform: Any = None) -> None:
        self._platform = research_platform
        self._state = ResearchAdapterState.DISCONNECTED
        self._lock = threading.Lock()
        self._factor_jobs: Dict[str, Dict[str, Any]] = {}
        self._backtest_jobs: Dict[str, Dict[str, Any]] = {}
        self._analysis_jobs: Dict[str, Dict[str, Any]] = {}
        self._report_jobs: Dict[str, Dict[str, Any]] = {}
        self._execution_count: int = 0

    @property
    def state(self) -> ResearchAdapterState:
        return self._state

    @property
    def total_jobs(self) -> int:
        return len(self._factor_jobs) + len(self._backtest_jobs) + len(self._analysis_jobs) + len(self._report_jobs)

    @property
    def execution_count(self) -> int:
        return self._execution_count

    async def connect(self) -> None:
        self._set_state(ResearchAdapterState.CONNECTING)
        try:
            if self._platform and hasattr(self._platform, "connect"):
                await self._platform.connect()
            self._set_state(ResearchAdapterState.CONNECTED)
            logger.info("ResearchRuntimeAdapter: connected")
        except Exception as exc:
            self._set_state(ResearchAdapterState.ERROR)
            raise

    async def disconnect(self) -> None:
        self._factor_jobs.clear()
        self._backtest_jobs.clear()
        self._analysis_jobs.clear()
        self._report_jobs.clear()
        self._set_state(ResearchAdapterState.DISCONNECTED)

    async def synchronize(self) -> Dict[str, Any]:
        return {"state": self._state.value, "total_jobs": self.total_jobs}

    # ------------------------------------------------------------------
    # Factor Research
    # ------------------------------------------------------------------

    async def schedule_factor_research(self, research_id: str, cron: Optional[str] = None, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Schedule a factor research computation job."""
        self._factor_jobs[research_id] = {
            "research_id": research_id, "cron": cron, "parameters": parameters or {},
            "scheduled_at": datetime.now(timezone.utc).isoformat(), "status": "scheduled",
        }
        self._execution_count += 1
        logger.info("ResearchRuntimeAdapter: scheduled factor research %s", research_id)
        return {"research_id": research_id, "status": "scheduled"}

    # ------------------------------------------------------------------
    # Backtest
    # ------------------------------------------------------------------

    async def schedule_backtest(self, backtest_id: str, cron: Optional[str] = None, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Schedule a backtest execution."""
        self._backtest_jobs[backtest_id] = {
            "backtest_id": backtest_id, "cron": cron, "parameters": parameters or {},
            "scheduled_at": datetime.now(timezone.utc).isoformat(), "status": "scheduled",
        }
        self._execution_count += 1
        logger.info("ResearchRuntimeAdapter: scheduled backtest %s", backtest_id)
        return {"backtest_id": backtest_id, "status": "scheduled"}

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    async def schedule_analysis(self, analysis_id: str, cron: Optional[str] = None, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Schedule a portfolio analysis job."""
        self._analysis_jobs[analysis_id] = {
            "analysis_id": analysis_id, "cron": cron, "parameters": parameters or {},
            "scheduled_at": datetime.now(timezone.utc).isoformat(), "status": "scheduled",
        }
        self._execution_count += 1
        return {"analysis_id": analysis_id, "status": "scheduled"}

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    async def schedule_report(self, report_id: str, cron: Optional[str] = None, template: Optional[str] = None) -> Dict[str, Any]:
        """Schedule a research report generation."""
        self._report_jobs[report_id] = {
            "report_id": report_id, "cron": cron, "template": template,
            "scheduled_at": datetime.now(timezone.utc).isoformat(), "status": "scheduled",
        }
        self._execution_count += 1
        return {"report_id": report_id, "status": "scheduled"}

    # ------------------------------------------------------------------
    # Research Pipeline
    # ------------------------------------------------------------------

    async def schedule_research_pipeline(self, pipeline_id: str, steps: List[str], cron: Optional[str] = None) -> Dict[str, Any]:
        """Schedule a multi-step research pipeline."""
        logger.info("ResearchRuntimeAdapter: scheduled pipeline %s (%d steps)", pipeline_id, len(steps))
        return {"pipeline_id": pipeline_id, "steps": steps, "status": "scheduled"}

    def _set_state(self, state: ResearchAdapterState) -> None:
        with self._lock:
            self._state = state
