"""Platform Health Checker — system-level health assessment for the AI Platform.

Checks all platform components:
    - AIGateway             — request routing health
    - ControlPlane           — orchestration health
    - LifecycleManager       — agent lifecycle health
    - RuntimeManager         — execution environment health
    - GlobalMemoryManager    — shared memory health
    - ModelRouter            — model routing health
    - ProviderManager        — provider connection health
    - TokenManager           — token tracking health
    - CostManager            — cost tracking health
    - BudgetController       — budget enforcement health
    - GuardrailEngine        — safety guardrail health
    - AuditCenter            — audit trail health
    - API Layer              — REST/gRPC/WS health
    - Platform Adapters      — adapter connectivity health
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    latency_ms: float = 0.0


@dataclass
class HealthReport:
    overall: HealthStatus = HealthStatus.UNKNOWN
    components: List[ComponentHealth] = field(default_factory=list)
    generated_at: float = field(default_factory=time.monotonic)

    @property
    def is_ok(self) -> bool:
        return self.overall == HealthStatus.OK

    def as_dict(self) -> Dict[str, Any]:
        return {
            "overall": self.overall.value,
            "is_ok": self.is_ok,
            "generated_at": self.generated_at,
            "components": [
                {"name": c.name, "status": c.status.value, "message": c.message, "latency_ms": round(c.latency_ms, 2)}
                for c in self.components
            ],
        }


class PlatformHealthChecker:
    """System-level health checker for the unified AI Platform.

    Checks all platform components and generates aggregated health reports
    with per-component status and recommendations.

    Usage:
        checker = PlatformHealthChecker()
        await checker.initialize()
        checker.register_check("gateway", my_check_fn)
        report = await checker.check_all()
    """

    # Platform components to check
    BUILTIN_COMPONENTS = [
        "ai_gateway",
        "control_plane",
        "lifecycle_manager",
        "runtime_manager",
        "global_memory_manager",
        "model_router",
        "provider_manager",
        "token_manager",
        "cost_manager",
        "budget_controller",
        "guardrail_engine",
        "audit_center",
        "rest_api",
        "grpc_api",
        "websocket_gateway",
        "workflow_adapter",
        "research_adapter",
    ]

    def __init__(self) -> None:
        self._checks: Dict[str, Any] = {}
        self._history: List[HealthReport] = []
        self._max_history: int = 200
        self._initialized: bool = False
        logger.info("PlatformHealthChecker created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("PlatformHealthChecker initialized")

    async def shutdown(self) -> None:
        self._checks.clear()
        self._history.clear()
        self._initialized = False
        logger.info("PlatformHealthChecker shutdown complete")

    def register_check(self, component_name: str, check_fn: Any) -> None:
        """Register a health check function for a component.

        check_fn should be an async callable that returns either:
        - ComponentHealth object
        - dict with 'status' and 'message' keys
        """
        self._checks[component_name] = check_fn

    async def check_all(self) -> HealthReport:
        """Run all registered health checks and return aggregated report."""
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
            except Exception as e:
                logger.error("Health check failed for %s: %s", name, e)
                components.append(ComponentHealth(name=name, status=HealthStatus.DOWN, message=str(e)))

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
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        return report

    async def check_component(self, component_name: str) -> Optional[ComponentHealth]:
        """Run a health check for a single component."""
        check_fn = self._checks.get(component_name)
        if not check_fn:
            return None
        try:
            start = time.monotonic()
            result = await check_fn()
            elapsed = (time.monotonic() - start) * 1000
            if isinstance(result, ComponentHealth):
                result.latency_ms = round(elapsed, 2)
                return result
            return ComponentHealth(
                name=component_name,
                status=HealthStatus(result.get("status", "unknown")),
                message=result.get("message", ""),
                latency_ms=round(elapsed, 2),
            )
        except Exception as e:
            return ComponentHealth(name=component_name, status=HealthStatus.DOWN, message=str(e))

    def get_latest(self) -> Optional[HealthReport]:
        return self._history[-1] if self._history else None

    def get_summary(self) -> Dict[str, Any]:
        latest = self.get_latest()
        return {
            "initialized": self._initialized,
            "registered_checks": sorted(self._checks.keys()),
            "latest_overall": latest.overall.value if latest else "unknown",
            "total_checks": len(self._checks),
        }

    @property
    def registered_components(self) -> List[str]:
        return sorted(self._checks.keys())
