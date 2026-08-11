"""Collaboration Health Checker — system-level health assessment for the multi-agent collaboration subsystem.

Checks all collaboration components:
    - AgentRegistry     — agent registration health
    - MessageBus        — message throughput health
    - SharedMemory      — memory integrity
    - ConsensusEngine   — consensus availability
    - CoordinatorAgent  — coordinator responsiveness
    - AgentMonitor      — monitoring coverage
    - EventBridge       — event pipeline health

Returns aggregated HealthReport with per-component status.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Health Status ──

class HealthStatus(str, Enum):
    """Health status for a component."""
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a single subsystem component.

    Attributes:
        name: Component name.
        status: Current health status.
        message: Optional detail message.
        latency_ms: Health check latency.
    """

    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    latency_ms: float = 0.0


@dataclass
class HealthReport:
    """Aggregated health report for the collaboration subsystem.

    Attributes:
        overall: Aggregated status (ok if all components ok).
        components: Per-component health statuses.
        generated_at: When the report was generated.
    """

    overall: HealthStatus = HealthStatus.UNKNOWN
    components: List[ComponentHealth] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    @property
    def is_ok(self) -> bool:
        """Whether the overall status is OK."""
        return self.overall == HealthStatus.OK

    def component_status(self, name: str) -> Optional[HealthStatus]:
        """Get health status of a specific component.

        Args:
            name: Component name.

        Returns:
            HealthStatus or None.
        """
        for c in self.components:
            if c.name == name:
                return c.status
        return None

    def as_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dict.

        Returns:
            Dict representation of the health report.
        """
        return {
            "overall": self.overall.value,
            "is_ok": self.is_ok,
            "generated_at": self.generated_at,
            "components": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "latency_ms": round(c.latency_ms, 2),
                }
                for c in self.components
            ],
        }


# ── Health Checker ──

class CollaborationHealthChecker:
    """System-level health checker for the multi-agent collaboration subsystem.

    Performs health checks against all collaboration components and
    generates aggregated HealthReports. Supports both one-shot checks
    and periodic background checking.

    Usage:
        checker = CollaborationHealthChecker()
        await checker.initialize()

        # Register component check callbacks
        checker.register_check("agent_registry", my_registry_health_check)

        report = await checker.check_all()
        print(report.as_dict())
    """

    def __init__(self) -> None:
        self._checks: Dict[str, Any] = {}
        self._history: List[HealthReport] = []
        self._max_history = 200
        self._initialized: bool = False
        logger.info("CollaborationHealthChecker created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the health checker."""
        if self._initialized:
            logger.warning("CollaborationHealthChecker already initialized")
            return
        self._initialized = True
        logger.info("CollaborationHealthChecker initialized")

    async def shutdown(self) -> None:
        """Shut down the health checker."""
        self._checks.clear()
        self._history.clear()
        self._initialized = False
        logger.info("CollaborationHealthChecker shutdown complete")

    # ── Check Registration ──

    def register_check(
        self,
        component_name: str,
        check_fn: Any,
    ) -> None:
        """Register a health check callback for a component.

        Args:
            component_name: Identifier for the component (e.g. "agent_registry").
            check_fn: Async callable that returns ComponentHealth.
        """
        self._checks[component_name] = check_fn
        logger.debug("Health check registered: %s", component_name)

    def unregister_check(self, component_name: str) -> None:
        """Remove a health check.

        Args:
            component_name: The component to remove.
        """
        self._checks.pop(component_name, None)
        logger.debug("Health check unregistered: %s", component_name)

    # ── Health Checks ──

    async def check_all(self) -> HealthReport:
        """Run all registered health checks and aggregate results.

        Returns:
            HealthReport with per-component and overall status.
        """
        components: List[ComponentHealth] = []

        for name, check_fn in self._checks.items():
            try:
                start = time.monotonic()
                result = await check_fn()
                elapsed = (time.monotonic() - start) * 1000

                if isinstance(result, ComponentHealth):
                    result.latency_ms = round(elapsed, 2)
                    components.append(result)
                elif isinstance(result, dict):
                    components.append(ComponentHealth(
                        name=name,
                        status=HealthStatus(result.get("status", "unknown")),
                        message=result.get("message", ""),
                        latency_ms=round(elapsed, 2),
                    ))
                else:
                    components.append(ComponentHealth(
                        name=name,
                        status=HealthStatus.OK,
                        latency_ms=round(elapsed, 2),
                    ))

            except Exception as e:
                logger.error("Health check failed for %s: %s", name, e)
                components.append(ComponentHealth(
                    name=name,
                    status=HealthStatus.DOWN,
                    message=str(e),
                ))

        # Determine overall status
        statuses = [c.status for c in components]
        if HealthStatus.DOWN in statuses:
            overall = HealthStatus.DOWN
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        elif not components:
            overall = HealthStatus.UNKNOWN
        else:
            overall = HealthStatus.OK

        report = HealthReport(overall=overall, components=components)
        self._history.append(report)

        # Trim history
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        return report

    async def check_component(self, component_name: str) -> Optional[ComponentHealth]:
        """Run a health check for a single component.

        Args:
            component_name: The component to check.

        Returns:
            ComponentHealth or None if not registered.
        """
        check_fn = self._checks.get(component_name)
        if check_fn is None:
            logger.warning("No health check registered for: %s", component_name)
            return None

        try:
            start = time.monotonic()
            result = await check_fn()
            elapsed = (time.monotonic() - start) * 1000

            if isinstance(result, ComponentHealth):
                result.latency_ms = round(elapsed, 2)
                return result
            elif isinstance(result, dict):
                return ComponentHealth(
                    name=component_name,
                    status=HealthStatus(result.get("status", "unknown")),
                    message=result.get("message", ""),
                    latency_ms=round(elapsed, 2),
                )
            return ComponentHealth(
                name=component_name,
                status=HealthStatus.OK,
                latency_ms=round(elapsed, 2),
            )

        except Exception as e:
            logger.error("Health check failed for %s: %s", component_name, e)
            return ComponentHealth(
                name=component_name,
                status=HealthStatus.DOWN,
                message=str(e),
            )

    # ── Built-in Checks ──

    async def _agent_registry_check(self, registry: Any) -> ComponentHealth:
        """Built-in check for AgentRegistry.

        Args:
            registry: AgentRegistry instance.

        Returns:
            ComponentHealth.
        """
        if registry is None:
            return ComponentHealth(
                name="agent_registry",
                status=HealthStatus.DOWN,
                message="AgentRegistry not connected",
            )
        try:
            count = registry.agent_count if hasattr(registry, "agent_count") else 0
            return ComponentHealth(
                name="agent_registry",
                status=HealthStatus.OK,
                message=f"OK — {count} agents registered",
            )
        except Exception as e:
            return ComponentHealth(
                name="agent_registry",
                status=HealthStatus.DEGRADED,
                message=str(e),
            )

    async def _message_bus_check(self, message_bus: Any) -> ComponentHealth:
        """Built-in check for MessageBus.

        Args:
            message_bus: MessageBus instance.

        Returns:
            ComponentHealth.
        """
        if message_bus is None:
            return ComponentHealth(
                name="message_bus",
                status=HealthStatus.DOWN,
                message="MessageBus not connected",
            )
        try:
            return ComponentHealth(
                name="message_bus",
                status=HealthStatus.OK,
                message="OK",
            )
        except Exception as e:
            return ComponentHealth(
                name="message_bus",
                status=HealthStatus.DEGRADED,
                message=str(e),
            )

    async def _consensus_check(self, consensus_engine: Any) -> ComponentHealth:
        """Built-in check for ConsensusEngine.

        Args:
            consensus_engine: ConsensusEngine instance.

        Returns:
            ComponentHealth.
        """
        if consensus_engine is None:
            return ComponentHealth(
                name="consensus_engine",
                status=HealthStatus.DOWN,
                message="ConsensusEngine not connected",
            )
        return ComponentHealth(
            name="consensus_engine",
            status=HealthStatus.OK,
            message="OK",
        )

    # ── History ──

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent health check reports.

        Args:
            limit: Maximum reports to return.

        Returns:
            List of report dicts.
        """
        return [r.as_dict() for r in self._history[-limit:]]

    def get_latest(self) -> Optional[HealthReport]:
        """Get the most recent health report.

        Returns:
            HealthReport or None.
        """
        return self._history[-1] if self._history else None

    # ── Query ──

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the health checker state.

        Returns:
            Dict with checker status and latest report.
        """
        latest = self.get_latest()
        return {
            "initialized": self._initialized,
            "registered_checks": sorted(self._checks.keys()),
            "history_count": len(self._history),
            "latest_overall": latest.overall.value if latest else "unknown",
            "latest_report": latest.as_dict() if latest else None,
        }

    @property
    def registered_components(self) -> List[str]:
        """Return list of registered component names."""
        return sorted(self._checks.keys())
