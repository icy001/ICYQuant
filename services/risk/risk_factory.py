"""
Risk factory — Legacy and Foundation layers.

The legacy ``RiskFactory`` creates ``RiskDomain`` instances. The
``RiskComponentFactory`` wires together all foundation-level risk
components for the production Risk Management Platform.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .risk_domain import RiskDomain

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Legacy Risk Factory
# ---------------------------------------------------------------------------


class RiskFactory:
    """Legacy risk domain factory (backwards-compatible)."""

    def create(self, domain_id: str) -> RiskDomain:
        return RiskDomain(
            domain_id=domain_id,
            name="Risk",
            version="0.3.0-beta3",
            status="ACTIVE",
        )


# ---------------------------------------------------------------------------
# Foundation Risk Component Factory
# ---------------------------------------------------------------------------


class RiskComponentFactory:
    """
    Foundation-level component factory for the Risk Management Platform.

    Creates and wires together all risk components with their
    dependencies: engine, runtime, lifecycle, executor, policy engine,
    profile manager, snapshot manager, recovery manager, controller,
    configuration manager, registry, scheduler, state manager, and
    metadata registry.

    Usage::

        factory = RiskComponentFactory(config={"platform_id": "RISK-01"})
        risk_engine = await factory.create_risk_engine()
        risk_runtime = await factory.create_risk_runtime()
    """

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._components: dict[str, Any] = {}

    # ---- Core Components ----

    async def create_risk_engine(self) -> Any:
        """Create the production RiskEngine."""
        from .risk_engine import RiskEngine

        component = RiskEngine(platform_id=self._config.get("platform_id", "RISK-01"))
        self._components["risk_engine"] = component
        logger.info("RiskEngine created.")
        return component

    async def create_risk_runtime(self) -> Any:
        """Create the RiskRuntime."""
        from .risk_runtime import RuntimeConfig, RiskRuntime

        component = RiskRuntime(config=RuntimeConfig())
        self._components["risk_runtime"] = component
        logger.info("RiskRuntime created.")
        return component

    async def create_risk_lifecycle(self) -> Any:
        """Create the RiskLifecycle manager."""
        from .risk_lifecycle import RiskLifecycle

        component = RiskLifecycle()
        self._components["risk_lifecycle"] = component
        logger.info("RiskLifecycle created.")
        return component

    async def create_risk_executor(self) -> Any:
        """Create the RiskExecutor."""
        from .risk_executor import RiskExecutor

        component = RiskExecutor()
        self._components["risk_executor"] = component
        logger.info("RiskExecutor created.")
        return component

    async def create_risk_policy_engine(self) -> Any:
        """Create the RiskPolicyEngine."""
        from .risk_policy import RiskPolicyEngine

        component = RiskPolicyEngine()
        self._components["risk_policy_engine"] = component
        logger.info("RiskPolicyEngine created.")
        return component

    async def create_risk_profile_manager(self) -> Any:
        """Create the RiskProfileManager."""
        from .risk_profile import RiskProfileManager

        component = RiskProfileManager()
        self._components["risk_profile_manager"] = component
        logger.info("RiskProfileManager created.")
        return component

    async def create_risk_snapshot_manager(self) -> Any:
        """Create the RiskSnapshotManager."""
        from .risk_snapshot import RiskSnapshotManager

        component = RiskSnapshotManager()
        self._components["risk_snapshot_manager"] = component
        logger.info("RiskSnapshotManager created.")
        return component

    async def create_risk_recovery(self) -> Any:
        """Create the RiskRecovery manager."""
        from .risk_recovery import RiskRecovery

        component = RiskRecovery()
        self._components["risk_recovery"] = component
        logger.info("RiskRecovery created.")
        return component

    async def create_risk_controller(self) -> Any:
        """Create the RiskController."""
        from .risk_controller import RiskController

        component = RiskController()
        self._components["risk_controller"] = component
        logger.info("RiskController created.")
        return component

    async def create_risk_config_manager(self) -> Any:
        """Create the RiskConfigManager."""
        from .risk_configuration import RiskConfigManager

        component = RiskConfigManager()
        self._components["risk_config_manager"] = component
        logger.info("RiskConfigManager created.")
        return component

    async def create_risk_manager(self) -> Any:
        """Create the foundation RiskManager."""
        from .risk_manager import RiskManager

        component = RiskManager()
        self._components["risk_manager"] = component
        logger.info("RiskManager (foundation) created.")
        return component

    async def create_risk_registry(self) -> Any:
        """Create the RiskRegistry."""
        from .risk_registry import RiskRegistry

        component = RiskRegistry()
        self._components["risk_registry"] = component
        logger.info("RiskRegistry created.")
        return component

    async def create_risk_scheduler(self) -> Any:
        """Create the RiskScheduler."""
        from .risk_scheduler import RiskScheduler

        component = RiskScheduler()
        self._components["risk_scheduler"] = component
        logger.info("RiskScheduler created.")
        return component

    async def create_risk_state_manager(self) -> Any:
        """Create the RiskStateManager."""
        from .risk_state import RiskStateManager

        component = RiskStateManager()
        self._components["risk_state_manager"] = component
        logger.info("RiskStateManager created.")
        return component

    async def create_risk_metadata_registry(self) -> Any:
        """Create the RiskMetadataRegistry."""
        from .risk_metadata import RiskMetadataRegistry

        component = RiskMetadataRegistry()
        self._components["risk_metadata_registry"] = component
        logger.info("RiskMetadataRegistry created.")
        return component

    async def create_control_plane(self) -> Any:
        """Create the RiskControlPlane."""
        from .control_plane import RiskControlPlane

        component = RiskControlPlane()
        self._components["control_plane"] = component
        logger.info("RiskControlPlane created.")
        return component

    async def create_risk_api(self) -> Any:
        """Create the RiskAPI."""
        from .api import RiskAPI

        component = RiskAPI()
        self._components["risk_api"] = component
        logger.info("RiskAPI created.")
        return component

    async def create_risk_metrics(self) -> Any:
        """Create the RiskPlatformMetrics."""
        from .metrics import RiskPlatformMetrics

        component = RiskPlatformMetrics()
        self._components["risk_metrics"] = component
        logger.info("RiskPlatformMetrics created.")
        return component

    async def create_risk_telemetry(self) -> Any:
        """Create the RiskTelemetry."""
        from .telemetry import RiskTelemetry

        component = RiskTelemetry()
        self._components["risk_telemetry"] = component
        logger.info("RiskTelemetry created.")
        return component

    async def create_risk_diagnostics(self) -> Any:
        """Create the RiskDiagnostics."""
        from .diagnostics import RiskDiagnostics

        component = RiskDiagnostics()
        self._components["risk_diagnostics"] = component
        logger.info("RiskDiagnostics created.")
        return component

    async def create_risk_health_checker(self) -> Any:
        """Create the RiskHealthChecker."""
        from .health import RiskHealthChecker

        component = RiskHealthChecker()
        self._components["risk_health_checker"] = component
        logger.info("RiskHealthChecker created.")
        return component

    async def create_risk_repository(self) -> Any:
        """Create the FoundationRiskRepository."""
        from .risk_repository import FoundationRiskRepository

        component = FoundationRiskRepository()
        self._components["risk_repository"] = component
        logger.info("FoundationRiskRepository created.")
        return component

    # ---- Bulk Creation ----

    async def create_all(self) -> dict[str, Any]:
        """Create all foundation components at once."""
        await self.create_risk_engine()
        await self.create_risk_runtime()
        await self.create_risk_lifecycle()
        await self.create_risk_executor()
        await self.create_risk_policy_engine()
        await self.create_risk_profile_manager()
        await self.create_risk_snapshot_manager()
        await self.create_risk_recovery()
        await self.create_risk_controller()
        await self.create_risk_config_manager()
        await self.create_risk_manager()
        await self.create_risk_registry()
        await self.create_risk_scheduler()
        await self.create_risk_state_manager()
        await self.create_risk_metadata_registry()
        await self.create_control_plane()
        await self.create_risk_api()
        await self.create_risk_metrics()
        await self.create_risk_telemetry()
        await self.create_risk_diagnostics()
        await self.create_risk_health_checker()
        await self.create_risk_repository()
        logger.info("All foundation components created.")
        return self._components

    def get_component(self, name: str) -> Optional[Any]:
        """Retrieve a previously created component."""
        return self._components.get(name)