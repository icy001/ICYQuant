"""AI Platform — Top-level AI Quant Intelligence Platform orchestrator.

Unifies all AI subsystems (Research, Agents, ML, Model Serving) with the trading
platform (Strategy, Risk, Portfolio, OMS/EMS) under a single control plane.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .ai_runtime import AIRuntime
from .ai_manager import AIManager
from .ai_controller import AIController
from .ai_gateway import AIGateway
from .ai_orchestrator import AIOrchestrator
from .ai_control_plane import AIControlPlane
from .ai_context import AIContext
from .ai_session import AISession
from .ai_policy import AIPolicy
from .ai_permissions import AIPermissions

logger = logging.getLogger(__name__)


class AIPlatformStatus(Enum):
    """AI Platform status lifecycle."""

    INITIALIZING = "initializing"
    CONNECTING = "connecting"
    READY = "ready"
    DEGRADED = "degraded"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"
    OFFLINE = "offline"


class AIPlatformMode(Enum):
    """AI Platform operating modes."""

    RESEARCH = "research"
    PAPER_TRADING = "paper_trading"
    LIVE = "live"
    BACKTEST = "backtest"
    AUDIT = "audit"


@dataclass
class AIPlatformConfig:
    """AI Platform configuration."""

    mode: AIPlatformMode = AIPlatformMode.RESEARCH
    enable_research: bool = True
    enable_agents: bool = True
    enable_ml: bool = True
    enable_model_serving: bool = True
    enable_strategy: bool = False
    enable_risk: bool = True
    enable_portfolio: bool = False
    enable_oms: bool = False
    enable_execution: bool = False
    enable_feedback_loop: bool = True
    enable_learning_loop: bool = False
    enable_decision_audit: bool = True
    max_concurrent_decisions: int = 10
    decision_timeout_seconds: float = 30.0
    require_approval: bool = True


class AIPlatform:
    """AI Quant Intelligence Platform — unified entry point.

    Integrates all AI capabilities with the trading platform through a single
    control plane. This is the top-level orchestrator that manages the complete
    AI lifecycle from research to execution feedback.

    Architecture:
        AI Control Plane
            ├── AI Orchestrator
            │   ├── Research Adapter
            │   ├── Agent Adapter
            │   ├── Feature Adapter
            │   ├── ML Adapter
            │   └── Model Serving Adapter
            ├── Intelligence Pipeline
            │   ├── Decision Pipeline
            │   ├── Signal Pipeline
            │   └── Prediction Pipeline
            ├── Decision Guard
            ├── Execution Guard
            ├── Approval Engine
            └── Feedback Loop

    Usage:
        platform = AIPlatform(config)
        await platform.start()
        decision = await platform.process_intelligence(session)
    """

    def __init__(self, config: Optional[AIPlatformConfig] = None) -> None:
        self.config = config or AIPlatformConfig()
        self.status = AIPlatformStatus.INITIALIZING
        self._start_time: Optional[datetime] = None

        # Core subsystems
        self.runtime = AIRuntime()
        self.manager = AIManager(self.config)
        self.controller = AIController(self.config)
        self.gateway = AIGateway(self.config)
        self.orchestrator = AIOrchestrator(self.config)
        self.control_plane = AIControlPlane(self.config)
        self.policy = AIPolicy(self.config)
        self.permissions = AIPermissions(self.config)

        # Statistics
        self._requests_total: int = 0
        self._decisions_total: int = 0
        self._signals_total: int = 0
        self._errors_total: int = 0
        self._sessions: Dict[str, AISession] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the AI Platform and all subsystems."""
        self.status = AIPlatformStatus.INITIALIZING
        self._start_time = datetime.now(timezone.utc)
        logger.info("AI Platform starting in mode=%s", self.config.mode.value)

        try:
            await self.runtime.start()
            self.status = AIPlatformStatus.CONNECTING
            logger.info("AI Runtime started")

            await self.manager.start()
            logger.info("AI Manager started")

            await self.controller.start()
            logger.info("AI Controller started")

            await self.gateway.start()
            logger.info("AI Gateway started")

            await self.orchestrator.start()
            logger.info("AI Orchestrator started")

            await self.control_plane.start()
            logger.info("AI Control Plane started")

            self.status = AIPlatformStatus.READY
            logger.info("AI Platform ready")

        except Exception as exc:
            self.status = AIPlatformStatus.ERROR
            logger.error("AI Platform start failed: %s", exc)
            raise

    async def stop(self) -> None:
        """Gracefully shut down the AI Platform."""
        self.status = AIPlatformStatus.SHUTTING_DOWN
        logger.info("AI Platform shutting down")

        for name, subsystem in [
            ("Control Plane", self.control_plane),
            ("Orchestrator", self.orchestrator),
            ("Gateway", self.gateway),
            ("Controller", self.controller),
            ("Manager", self.manager),
            ("Runtime", self.runtime),
        ]:
            try:
                await subsystem.stop()
            except Exception as exc:
                logger.warning("Error stopping %s: %s", name, exc)

        self.status = AIPlatformStatus.OFFLINE
        logger.info("AI Platform offline")

    # ------------------------------------------------------------------
    # Intelligence Processing
    # ------------------------------------------------------------------

    async def process_intelligence(
        self,
        session: AISession,
    ) -> AIContext:
        """Process a complete intelligence cycle for a session.

        This is the main entry point for the AI platform. It runs the full
        intelligence pipeline: research → agents → features → prediction →
        signal → strategy → risk → decision.

        Args:
            session: AI session containing the request context.

        Returns:
            AIContext with the complete decision trace.
        """
        self._requests_total += 1

        if self.status != AIPlatformStatus.READY:
            if self.status == AIPlatformStatus.DEGRADED:
                logger.warning("Processing in degraded mode")
            else:
                raise RuntimeError(f"AI Platform not ready: {self.status}")

        context = AIContext(session=session)

        try:
            # Permission check
            await self.permissions.check(session, context)

            # Policy evaluation
            await self.policy.evaluate(session, context)

            # Full intelligence pipeline through orchestrator
            context = await self.orchestrator.process(session, context)

            self._decisions_total += 1
            if context.has_signal:
                self._signals_total += 1

            # Audit trail
            if self.config.enable_decision_audit:
                await self._audit_decision(context)

            return context

        except Exception as exc:
            self._errors_total += 1
            logger.error("Intelligence processing failed: %s", exc, exc_info=True)
            context.add_error(str(exc))
            raise

    # ------------------------------------------------------------------
    # Session Management
    # ------------------------------------------------------------------

    async def create_session(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AISession:
        """Create a new AI session."""
        session = AISession(
            session_id=session_id,
            metadata=metadata or {},
            mode=self.config.mode,
        )
        self._sessions[session.session_id] = session
        return session

    async def get_session(self, session_id: str) -> Optional[AISession]:
        """Retrieve an existing session by ID."""
        return self._sessions.get(session_id)

    async def close_session(self, session_id: str) -> None:
        """Close and cleanup a session."""
        session = self._sessions.pop(session_id, None)
        if session:
            await session.close()

    # ------------------------------------------------------------------
    # Direct Access
    # ------------------------------------------------------------------

    async def research(self, session: AISession) -> AIContext:
        """Run AI research for a session."""
        return await self.orchestrator.research(session)

    async def predict(self, session: AISession) -> AIContext:
        """Run model prediction for a session."""
        return await self.orchestrator.predict(session)

    async def generate_signal(self, session: AISession) -> AIContext:
        """Generate a trading signal for a session."""
        return await self.orchestrator.generate_signal(session)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _audit_decision(self, context: AIContext) -> None:
        """Record the decision audit trail."""
        from .decision_audit import DecisionAudit

        audit = DecisionAudit(context)
        await audit.record()

    # ------------------------------------------------------------------
    # Health & Metrics
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        """Platform health status."""
        return {
            "status": self.status.value,
            "mode": self.config.mode.value,
            "uptime_seconds": (
                (datetime.now(timezone.utc) - self._start_time).total_seconds()
                if self._start_time
                else 0
            ),
            "requests_total": self._requests_total,
            "decisions_total": self._decisions_total,
            "signals_total": self._signals_total,
            "errors_total": self._errors_total,
            "active_sessions": len(self._sessions),
            "subsystems": {
                "runtime": await self.runtime.health(),
                "manager": await self.manager.health(),
                "controller": await self.controller.health(),
                "gateway": await self.gateway.health(),
                "orchestrator": await self.orchestrator.health(),
                "control_plane": await self.control_plane.health(),
            },
        }

    async def metrics(self) -> Dict[str, Any]:
        """Platform metrics."""
        return {
            "icyquant_ai_requests_total": self._requests_total,
            "icyquant_ai_decisions_total": self._decisions_total,
            "icyquant_ai_signals_total": self._signals_total,
            "icyquant_ai_errors_total": self._errors_total,
            "icyquant_ai_active_sessions": len(self._sessions),
        }
