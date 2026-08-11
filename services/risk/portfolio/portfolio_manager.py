"""
Portfolio Manager — Top-level orchestrator for the portfolio risk platform.

Coordinates all portfolio subsystems (risk engine, monitors, alert
center, action engine) and provides the unified external API.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from .portfolio_risk_engine import PortfolioRiskEngine
from .portfolio_monitor import PortfolioMonitor, MonitorConfig
from .portfolio_runtime import PortfolioRuntime, PortfolioRuntimeConfig
from .portfolio_snapshot import PortfolioSnapshot
from .portfolio_health import PortfolioHealthMonitor
from .risk_alert_center import RiskAlertCenter
from .risk_action_engine import RiskActionEngine

logger = logging.getLogger(__name__)


class PortfolioManager:
    """
    Top-level orchestrator for the portfolio risk platform.

    Coordinates all portfolio subsystems and provides a unified
    API for portfolio risk management, monitoring, and automated
    risk actions.

    Architecture::

        PortfolioManager
            ├── PortfolioRiskEngine
            ├── PortfolioMonitor
            ├── RiskAlertCenter
            ├── RiskActionEngine
            ├── PortfolioRuntime
            └── PortfolioHealthMonitor

    Usage::

        mgr = PortfolioManager()
        await mgr.initialize()
        await mgr.start()

        snapshot = build_snapshot(...)
        assessment = await mgr.evaluate(snapshot)
        await mgr.stop()
    """

    def __init__(
        self,
        risk_engine: Optional[PortfolioRiskEngine] = None,
        monitor: Optional[PortfolioMonitor] = None,
        alert_center: Optional[RiskAlertCenter] = None,
        action_engine: Optional[RiskActionEngine] = None,
        runtime: Optional[PortfolioRuntime] = None,
        health: Optional[PortfolioHealthMonitor] = None,
    ) -> None:
        self._risk_engine = risk_engine or PortfolioRiskEngine()
        self._monitor = monitor or PortfolioMonitor()
        self._alert_center = alert_center or RiskAlertCenter()
        self._action_engine = action_engine or RiskActionEngine()
        self._runtime = runtime or PortfolioRuntime()
        self._health = health or PortfolioHealthMonitor()
        self._initialized = False
        self._lock = asyncio.Lock()

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize all portfolio subsystems."""
        if self._initialized:
            return
        logger.info("PortfolioManager initializing all subsystems...")

        await asyncio.gather(
            self._runtime.initialize(),
            self._risk_engine.initialize(),
            self._monitor.initialize(),
            self._alert_center.initialize(),
            self._action_engine.initialize(),
            self._health.initialize(),
        )

        # Register subsystems for health monitoring
        self._health.register_subsystem("runtime", self._runtime)
        self._health.register_subsystem("risk_engine", self._risk_engine)
        self._health.register_subsystem("monitor", self._monitor)
        self._health.register_subsystem("alert_center", self._alert_center)
        self._health.register_subsystem("action_engine", self._action_engine)

        self._initialized = True
        logger.info("PortfolioManager initialized.")

    async def start(self) -> None:
        """Start the portfolio platform."""
        if not self._initialized:
            await self.initialize()
        await self._runtime.start()
        await self._monitor.start()
        logger.info("PortfolioManager started.")

    async def stop(self) -> None:
        """Stop the portfolio platform."""
        await self._action_engine.stop()
        await self._alert_center.stop()
        await self._monitor.stop()
        await self._runtime.stop()
        await self._health.stop()
        self._initialized = False
        logger.info("PortfolioManager stopped.")

    # ---- Core API ----

    async def evaluate(self, snapshot: PortfolioSnapshot) -> dict[str, Any]:
        """
        Full portfolio risk evaluation pipeline.

        Pipeline: Snapshot → Risk Engine → Monitor → Alerts → Actions

        Returns a comprehensive assessment with all intermediate results.
        """
        if not self._initialized:
            await self.initialize()

        import time
        t_start = time.perf_counter()

        # Step 1: Portfolio Risk Engine — aggregate risk assessment
        risk_assessment = await self._risk_engine.evaluate(snapshot)

        # Step 2: Monitor — threshold checks against limits
        monitor_result = await self._monitor.evaluate(snapshot)

        # Step 3: Alert Center — generate alerts from breaches
        if monitor_result.breaches or risk_assessment.get("breaches"):
            alerts = await self._alert_center.process_breaches(
                breaches=monitor_result.breaches + risk_assessment.get("breaches", []),
                risk_level=monitor_result.risk_level.value,
                snapshot=snapshot,
            )

            # Step 4: Risk Action Engine — take automated actions
            if alerts:
                await self._action_engine.process_alerts(alerts)

        evaluation_time_ms = (time.perf_counter() - t_start) * 1000

        result = {
            "risk_assessment": risk_assessment,
            "monitor_result": {
                "risk_level": monitor_result.risk_level.value,
                "risk_score": monitor_result.risk_score,
                "breaches": monitor_result.breaches,
                "warnings": monitor_result.warnings,
            },
            "evaluation_time_ms": evaluation_time_ms,
            "snapshot_id": snapshot.snapshot_id,
            "account_id": snapshot.account_id,
        }

        logger.info(
            f"Portfolio evaluation complete: score={monitor_result.risk_score:.1f}, "
            f"level={monitor_result.risk_level.value}, time={evaluation_time_ms:.1f}ms"
        )
        return result

    async def monitor(self, snapshot: PortfolioSnapshot) -> dict[str, Any]:
        """Run a lightweight monitoring pass only."""
        result = await self._monitor.evaluate(snapshot)
        return {
            "risk_level": result.risk_level.value,
            "risk_score": result.risk_score,
            "breaches": result.breaches,
            "warnings": result.warnings,
        }

    # ---- Query ----

    async def get_health(self) -> dict[str, Any]:
        """Get platform-wide health report."""
        report = await self._health.check()
        return report.to_dict()

    async def get_runtime_state(self) -> dict[str, Any]:
        """Get runtime state."""
        state = self._runtime.get_state()
        return {
            "status": state.status.value,
            "evaluations_active": state.evaluations_active,
            "evaluations_completed": state.evaluations_completed,
            "evaluations_failed": state.evaluations_failed,
            "uptime_seconds": state.uptime_seconds,
        }

    async def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics."""
        monitor_stats = await self._monitor.get_stats()
        return {
            "runtime": await self._runtime.health_check(),
            "monitor": monitor_stats,
            "actions": await self._action_engine.get_stats(),
            "alerts": await self._alert_center.get_stats(),
        }

    # ---- Control ----

    async def pause_all(self) -> None:
        """Pause all portfolio operations."""
        await self._runtime.pause()
        await self._monitor.pause()
        logger.warning("PortfolioManager: all operations paused.")

    async def resume_all(self) -> None:
        """Resume all portfolio operations."""
        await self._runtime.resume()
        await self._monitor.resume()
        logger.info("PortfolioManager: all operations resumed.")

    async def emergency_stop(self, reason: str = "") -> None:
        """Emergency stop — halt all operations immediately."""
        logger.critical(f"PortfolioManager: EMERGENCY STOP triggered. Reason: {reason}")
        await self._action_engine.trigger_kill_switch(reason)
        await self.stop()
