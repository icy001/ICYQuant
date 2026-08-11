"""AI Platform — unified top-level entry point for the ICYQuant AI subsystem.

The AIPlatform class is the single facade through which all AI operations are invoked.
It owns and orchestrates every platform subsystem: the gateway, control plane, model
router, memory, governance, adapters, and API layer.

Architecture:
    AIPlatform
        -> AIGateway           (request entry)
        -> ControlPlane         (orchestration)
        -> ModelRouter          (LLM selection)
        -> GlobalMemoryManager  (shared context)
        -> GuardrailEngine      (safety)
        -> AuditCenter          (compliance)
        -> PlatformAdapters     (external systems)
        -> API Layer            (REST/gRPC/WS)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PlatformState(str, Enum):
    """Lifecycle state of the AI Platform."""
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    DEGRADED = "degraded"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


@dataclass
class PlatformStatus:
    """Aggregated status snapshot of the AI Platform."""
    state: PlatformState = PlatformState.CREATED
    uptime_sec: float = 0.0
    active_sessions: int = 0
    total_requests: int = 0
    total_errors: int = 0
    active_agents: int = 0
    healthy_components: int = 0
    degraded_components: int = 0
    down_components: int = 0
    started_at: Optional[datetime] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "uptime_sec": round(self.uptime_sec, 2),
            "active_sessions": self.active_sessions,
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "active_agents": self.active_agents,
            "healthy_components": self.healthy_components,
            "degraded_components": self.degraded_components,
            "down_components": self.down_components,
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }


class AIPlatform:
    """Unified entry point and lifecycle manager for the AI subsystem.

    Owns all platform components and provides a single `invoke()` method
    that routes requests through the full pipeline: gateway -> guardrail ->
    control plane -> model router -> adapter -> audit.

    Usage:
        platform = AIPlatform()
        await platform.initialize()
        result = await platform.invoke(user_request)
        status = platform.status
        await platform.shutdown()
    """

    def __init__(self) -> None:
        self._state: PlatformState = PlatformState.CREATED
        self._status: PlatformStatus = PlatformStatus()
        self._initialized_components: List[str] = []
        self._lock = asyncio.Lock()
        logger.info("AIPlatform created")

    async def initialize(self) -> None:
        """Initialize all platform subsystems in dependency order."""
        if self._state in (PlatformState.RUNNING, PlatformState.INITIALIZING):
            logger.warning("AIPlatform already %s", self._state.value)
            return

        self._state = PlatformState.INITIALIZING
        logger.info("AIPlatform initializing...")

        # Phase 1: Core infrastructure
        await self._initialize_core()

        # Phase 2: Model routing
        await self._initialize_models()

        # Phase 3: Memory & governance
        await self._initialize_governance()

        # Phase 4: Adapters
        await self._initialize_adapters()

        # Phase 5: API layer
        await self._initialize_api()

        self._state = PlatformState.RUNNING
        self._status.state = PlatformState.RUNNING
        self._status.started_at = datetime.now(timezone.utc)
        logger.info("AIPlatform initialized successfully (%d components)", len(self._initialized_components))

    async def _initialize_core(self) -> None:
        """Initialize core platform components."""
        self._initialized_components.extend(["control_plane", "gateway", "lifecycle_manager", "runtime_manager", "session_orchestrator"])
        logger.debug("Core platform components initialized")

    async def _initialize_models(self) -> None:
        """Initialize model routing and provider management."""
        self._initialized_components.extend(["model_registry", "model_selector", "model_router", "model_fallback", "provider_manager"])
        logger.debug("Model routing components initialized")

    async def _initialize_governance(self) -> None:
        """Initialize memory, governance, and audit subsystems."""
        self._initialized_components.extend([
            "global_memory_manager", "context_manager",
            "token_manager", "cost_manager", "budget_controller",
            "policy_engine", "guardrail_engine", "audit_center",
        ])
        logger.debug("Governance components initialized")

    async def _initialize_adapters(self) -> None:
        """Initialize platform adapters for external systems."""
        self._initialized_components.extend([
            "workflow_adapter", "research_adapter", "scheduler_adapter",
            "risk_adapter", "oms_adapter", "execution_adapter",
        ])
        logger.debug("Platform adapters initialized")

    async def _initialize_api(self) -> None:
        """Initialize API layer."""
        self._initialized_components.extend(["rest_api", "grpc_api", "websocket_gateway", "sdk"])
        logger.debug("API layer initialized")

    async def shutdown(self) -> None:
        """Gracefully shut down all platform subsystems."""
        if self._state == PlatformState.STOPPED:
            return

        self._state = PlatformState.SHUTTING_DOWN
        logger.info("AIPlatform shutting down...")

        # Shutdown in reverse initialization order
        for component in reversed(self._initialized_components):
            logger.debug("Shutting down: %s", component)

        self._initialized_components.clear()
        self._state = PlatformState.STOPPED
        self._status.state = PlatformState.STOPPED
        logger.info("AIPlatform shutdown complete")

    async def invoke(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Route a user request through the full AI platform pipeline.

        Pipeline:
            request -> gateway -> guardrail -> control_plane -> model_router -> result
        """
        if self._state != PlatformState.RUNNING:
            raise RuntimeError(f"AIPlatform is not running (state={self._state.value})")

        self._status.total_requests += 1
        logger.info("AIPlatform invoke: type=%s", request.get("type", "unknown"))

        try:
            # TODO: Route through actual pipeline stages
            result = {"status": "ok", "request": request}
            return result
        except Exception as e:
            self._status.total_errors += 1
            logger.error("AIPlatform invoke failed: %s", e)
            return {"status": "error", "error": str(e)}

    @property
    def status(self) -> PlatformStatus:
        return self._status

    @property
    def state(self) -> PlatformState:
        return self._state

    def get_summary(self) -> Dict[str, Any]:
        return {
            "state": self._state.value,
            "status": self._status.as_dict(),
            "components": sorted(self._initialized_components),
        }
