"""AI Manager — Lifecycle and subsystem management for the AI Platform.

Manages initialization, health monitoring, version tracking, and dependency
management across all AI subsystems.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .ai_platform import AIPlatformConfig

logger = logging.getLogger(__name__)


@dataclass
class SubsystemInfo:
    """Information about a registered subsystem."""

    name: str
    version: str
    status: str = "uninitialized"
    healthy: bool = False
    last_check: Optional[datetime] = None
    errors: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DependencyInfo:
    """Dependency relationship between subsystems."""

    name: str
    depends_on: List[str]
    required: bool = True
    healthy: bool = False


class AIManager:
    """AI Manager — manages all AI subsystem lifecycles and dependencies.

    Responsibilities:
        - Register and track subsystem versions
        - Health check orchestration
        - Dependency resolution and ordering
        - Startup/shutdown sequencing
        - Configuration management
    """

    def __init__(self, config: "AIPlatformConfig") -> None:
        self.config = config
        self._subsystems: Dict[str, SubsystemInfo] = {}
        self._dependencies: Dict[str, DependencyInfo] = {}
        self._started = False
        self._start_time: Optional[datetime] = None

    async def start(self) -> None:
        """Initialize all AI subsystems in dependency order."""
        self._start_time = datetime.now(timezone.utc)
        logger.info("AI Manager starting")

        self._register_subsystems()
        await self._start_subsystems()
        self._started = True

        logger.info("AI Manager ready (%d subsystems)", len(self._subsystems))

    async def stop(self) -> None:
        """Shutdown all subsystems in reverse dependency order."""
        logger.info("AI Manager stopping")
        self._started = False

        for name in reversed(self._dependency_order()):
            subsystem = self._subsystems.get(name)
            if subsystem:
                subsystem.status = "stopped"
                logger.debug("Stopped subsystem: %s", name)

        logger.info("AI Manager stopped")

    # ------------------------------------------------------------------
    # Subsystem Registration
    # ------------------------------------------------------------------

    def _register_subsystems(self) -> None:
        """Register all AI subsystems with their dependencies."""
        # Core AI subsystems
        self.register_subsystem(
            "ai_research",
            version="0.4.0",
            metadata={"category": "ai", "critical": False},
        )
        self.register_subsystem(
            "ai_agent",
            version="0.4.0",
            metadata={"category": "ai", "critical": False},
        )
        self.register_subsystem(
            "feature_store",
            version="0.4.0",
            metadata={"category": "data", "critical": True},
        )
        self.register_subsystem(
            "ml_pipeline",
            version="0.4.0",
            metadata={"category": "ai", "critical": False},
        )
        self.register_subsystem(
            "model_serving",
            version="0.4.0",
            metadata={"category": "ai", "critical": True},
        )

        # Platform subsystems
        self.register_subsystem(
            "data_platform",
            version="0.4.0",
            metadata={"category": "data", "critical": True},
        )
        self.register_subsystem(
            "strategy",
            version="0.4.0",
            metadata={"category": "trading", "critical": False},
        )
        self.register_subsystem(
            "risk",
            version="0.4.0",
            metadata={"category": "trading", "critical": True},
        )
        self.register_subsystem(
            "portfolio",
            version="0.4.0",
            metadata={"category": "trading", "critical": False},
        )
        self.register_subsystem(
            "oms",
            version="0.4.0",
            metadata={"category": "execution", "critical": True},
        )
        self.register_subsystem(
            "execution",
            version="0.4.0",
            metadata={"category": "execution", "critical": True},
        )

        # Register dependencies
        self.register_dependency("ai_research", depends_on=["data_platform"])
        self.register_dependency("ai_agent", depends_on=["ai_research"])
        self.register_dependency("feature_store", depends_on=["data_platform"])
        self.register_dependency("ml_pipeline", depends_on=["feature_store"])
        self.register_dependency("model_serving", depends_on=["ml_pipeline", "feature_store"])
        self.register_dependency("strategy", depends_on=["model_serving", "data_platform"])
        self.register_dependency("risk", depends_on=["strategy", "portfolio"])
        self.register_dependency("portfolio", depends_on=["strategy"])
        self.register_dependency("oms", depends_on=["risk"])
        self.register_dependency("execution", depends_on=["oms"])

    def register_subsystem(
        self,
        name: str,
        version: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a subsystem."""
        self._subsystems[name] = SubsystemInfo(
            name=name,
            version=version,
            metadata=metadata or {},
        )
        logger.debug("Registered subsystem: %s v%s", name, version)

    def register_dependency(
        self,
        name: str,
        depends_on: List[str],
        required: bool = True,
    ) -> None:
        """Register dependencies for a subsystem."""
        self._dependencies[name] = DependencyInfo(
            name=name,
            depends_on=depends_on,
            required=required,
        )
        logger.debug("Registered dependency: %s → %s", name, depends_on)

    # ------------------------------------------------------------------
    # Subsystem Lifecycle
    # ------------------------------------------------------------------

    def _dependency_order(self) -> List[str]:
        """Topological sort of subsystems by dependency order."""
        visited: set = set()
        order: List[str] = []

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            dep = self._dependencies.get(name)
            if dep:
                for d in dep.depends_on:
                    if d in self._subsystems:
                        visit(d)
            order.append(name)

        for name in self._subsystems:
            visit(name)

        return order

    async def _start_subsystems(self) -> None:
        """Start subsystems in dependency order."""
        for name in self._dependency_order():
            subsystem = self._subsystems[name]
            try:
                subsystem.status = "initializing"

                # Check dependencies
                dep_info = self._dependencies.get(name)
                if dep_info:
                    deps_ok = all(
                        self._subsystems[d].status == "ready"
                        for d in dep_info.depends_on
                        if d in self._subsystems
                    )
                    if not deps_ok and dep_info.required:
                        subsystem.status = "error"
                        subsystem.errors.append({
                            "message": "Dependency not ready",
                            "depends_on": dep_info.depends_on,
                        })
                        continue

                subsystem.status = "ready"
                subsystem.healthy = True
                subsystem.last_check = datetime.now(timezone.utc)
                logger.debug("Started subsystem: %s", name)

            except Exception as exc:
                subsystem.status = "error"
                subsystem.errors.append({"message": str(exc)})
                logger.warning("Failed to start subsystem %s: %s", name, exc)

    # ------------------------------------------------------------------
    # Subsystem Status
    # ------------------------------------------------------------------

    def get_subsystem(self, name: str) -> Optional[SubsystemInfo]:
        """Get subsystem info by name."""
        return self._subsystems.get(name)

    def get_all_subsystems(self) -> Dict[str, SubsystemInfo]:
        """Get all registered subsystems."""
        return dict(self._subsystems)

    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Get the full dependency graph."""
        return {
            name: dep.depends_on.copy()
            for name, dep in self._dependencies.items()
        }

    def check_dependencies(self, name: str) -> Dict[str, bool]:
        """Check if all dependencies of a subsystem are healthy."""
        dep_info = self._dependencies.get(name)
        if not dep_info:
            return {}

        result = {}
        for dep_name in dep_info.depends_on:
            sub = self._subsystems.get(dep_name)
            result[dep_name] = sub is not None and sub.healthy
        return result

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        """Manager health status."""
        total = len(self._subsystems)
        healthy = sum(1 for s in self._subsystems.values() if s.healthy)
        critical = sum(
            1 for s in self._subsystems.values()
            if s.metadata.get("critical") and not s.healthy
        )

        return {
            "subsystems_total": total,
            "subsystems_healthy": healthy,
            "subsystems_unhealthy": total - healthy,
            "critical_failures": critical,
            "status": "healthy" if critical == 0 else "degraded",
            "details": {
                name: {
                    "version": s.version,
                    "status": s.status,
                    "healthy": s.healthy,
                    "critical": s.metadata.get("critical", False),
                }
                for name, s in self._subsystems.items()
            },
        }
