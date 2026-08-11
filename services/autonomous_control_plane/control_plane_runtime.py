"""
Control Plane Runtime — Singleton runtime for the Control Plane subsystem.

Provides lifecycle management for all Control Plane engines and serves
as the unified entry point for the governance layer.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RuntimeState(Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class RuntimeConfig:
    """Configuration for the Control Plane Runtime."""
    # Engine flags
    enable_policy_engine: bool = True
    enable_autonomy_engine: bool = True
    enable_decision_engine: bool = True
    enable_budget_manager: bool = True
    enable_lifecycle_engine: bool = True
    enable_promotion_engine: bool = True
    enable_approval_engine: bool = True
    enable_permission_engine: bool = True
    enable_audit_engine: bool = True
    enable_incident_manager: bool = True
    enable_health_monitor: bool = True
    enable_safety_layer: bool = True

    # Budget defaults
    daily_compute_budget: float = 100.0
    daily_experiment_budget: int = 500
    daily_strategy_budget: int = 200
    daily_execution_budget: float = 1_000_000.0

    # Autonomy defaults
    default_autonomy_level: int = 2

    # Policy
    policy_reload_interval_seconds: int = 300
    strict_mode: bool = True

    # Safety
    circuit_breaker_cooldown_seconds: int = 300
    kill_switch_requires_manual_reset: bool = True

    # Audit
    audit_retention_days: int = 2555  # ~7 years


class ControlPlaneRuntime:
    """
    Singleton runtime for the Autonomous Control Plane.

    Manages the lifecycle of all governance engines and serves as the
    central entry point for control plane operations.
    """

    _instance: Optional["ControlPlaneRuntime"] = None

    def __init__(self, config: Optional[RuntimeConfig] = None):
        self._config = config or RuntimeConfig()
        self._state = RuntimeState.CREATED
        self._started_at = 0.0

        # Engine instances (lazy)
        self._control_plane = None
        self._engines: dict[str, Any] = {}

        ControlPlaneRuntime._instance = self

    @classmethod
    def instance(cls) -> Optional["ControlPlaneRuntime"]:
        return cls._instance

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state == RuntimeState.RUNNING

    @property
    def config(self) -> RuntimeConfig:
        return self._config

    @property
    def control_plane(self):
        return self._control_plane

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialize and start all Control Plane engines."""
        if self._state == RuntimeState.RUNNING:
            logger.warning("Runtime already running")
            return

        self._state = RuntimeState.INITIALIZING
        self._started_at = time.time()
        logger.info("ControlPlaneRuntime starting...")

        try:
            await self._build_control_plane()
            await self._control_plane.start()
            await self._start_health_checks()
            self._state = RuntimeState.RUNNING
            logger.info("ControlPlaneRuntime RUNNING")
        except Exception:
            self._state = RuntimeState.ERROR
            logger.exception("ControlPlaneRuntime failed to start")
            raise

    async def stop(self) -> None:
        """Gracefully stop the runtime."""
        self._state = RuntimeState.STOPPING
        logger.info("ControlPlaneRuntime stopping...")

        if self._control_plane:
            await self._control_plane.stop()

        self._state = RuntimeState.STOPPED
        logger.info("ControlPlaneRuntime STOPPED")

    # ------------------------------------------------------------------
    # Engine Builder
    # ------------------------------------------------------------------

    async def _build_control_plane(self):
        """Lazily build the Control Plane with required engines."""

        # Import here to avoid circular dependencies
        from .control_plane import ControlPlane

        kwargs = {}

        if self._config.enable_policy_engine:
            from .policy_engine import PolicyEngine
            kwargs["policy_engine"] = PolicyEngine()

        if self._config.enable_autonomy_engine:
            from .autonomy_engine import AutonomyEngine
            kwargs["autonomy_engine"] = AutonomyEngine()

        if self._config.enable_decision_engine:
            from .decision_engine import DecisionEngine
            kwargs["decision_engine"] = DecisionEngine()

        if self._config.enable_budget_manager:
            from .research_budget_manager import ResearchBudgetManager
            kwargs["budget_manager"] = ResearchBudgetManager(
                compute_budget=self._config.daily_compute_budget,
                experiment_budget=self._config.daily_experiment_budget,
                strategy_budget=self._config.daily_strategy_budget,
                execution_budget=self._config.daily_execution_budget,
            )

        if self._config.enable_lifecycle_engine:
            from .model_lifecycle import ModelLifecycle
            kwargs["lifecycle_engine"] = ModelLifecycle()

        if self._config.enable_promotion_engine:
            from .promotion_engine import PromotionEngine
            kwargs["promotion_engine"] = PromotionEngine()

        if self._config.enable_approval_engine:
            from .approval_engine import ApprovalEngine
            kwargs["approval_engine"] = ApprovalEngine()

        if self._config.enable_permission_engine:
            from .permission_engine import PermissionEngine
            kwargs["permission_engine"] = PermissionEngine()

        if self._config.enable_audit_engine:
            from .audit_engine import AuditEngine
            kwargs["audit_engine"] = AuditEngine(
                retention_days=self._config.audit_retention_days
            )

        if self._config.enable_incident_manager:
            from .incident_manager import IncidentManager
            kwargs["incident_manager"] = IncidentManager()

        if self._config.enable_health_monitor:
            from .system_health import SystemHealth
            kwargs["health_monitor"] = SystemHealth()

        if self._config.enable_safety_layer:
            from .global_kill_switch import GlobalKillSwitch
            kwargs["safety_layer"] = GlobalKillSwitch()

        self._control_plane = ControlPlane(**kwargs)

    async def _start_health_checks(self):
        """Start periodic health checks."""
        asyncio.create_task(self._health_loop())

    async def _health_loop(self):
        """Background health monitoring loop."""
        while self._state == RuntimeState.RUNNING:
            try:
                if self._control_plane and self._control_plane.health_monitor:
                    health = await self._control_plane.health_monitor.check()
                    if health.get("overall") == "CRITICAL":
                        logger.critical("Health check CRITICAL — considering restrictions")
            except Exception:
                logger.exception("Health check loop error")
            await asyncio.sleep(30)

    # ------------------------------------------------------------------
    # Decision API
    # ------------------------------------------------------------------

    async def evaluate(self, context: dict) -> dict:
        """Evaluate a decision through the control plane."""
        from .control_plane import ControlPlaneContext
        cp_context = ControlPlaneContext(**context)
        decision = await self._control_plane.evaluate(cp_context)
        return {
            "trace_id": cp_context.trace_id,
            "decision": decision.value,
            "timestamp": time.time(),
        }

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def runtime_stats(self) -> dict:
        base = {
            "state": self._state.value,
            "uptime_seconds": time.time() - self._started_at if self._started_at else 0,
        }
        if self._control_plane:
            base["control_plane"] = self._control_plane.stats()
        return base
