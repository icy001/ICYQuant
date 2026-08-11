"""
Deployment Manager — Strategy package deployment orchestration.

Handles the complete deployment pipeline: package validation,
target selection, deployment execution, and status tracking.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DeploymentStatus(str, Enum):
    """Deployment status."""
    PENDING = "pending"
    VALIDATING = "validating"
    VALIDATED = "validated"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    CANARY = "canary"
    ROLLING_OUT = "rolling_out"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


@dataclass
class DeploymentPackage:
    """Strategy deployment package."""
    strategy_id: str
    version: str
    package_hash: str
    package_path: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DeploymentTarget:
    """Deployment target specification."""
    target_id: str
    target_type: str = "process"  # process, container, cluster
    host: str = "localhost"
    port: int = 0
    resources: dict[str, Any] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class DeploymentRecord:
    """Tracks a single deployment operation."""
    deployment_id: str
    strategy_id: str
    version: str
    status: DeploymentStatus = DeploymentStatus.PENDING
    target: Optional[DeploymentTarget] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    stages: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class DeploymentManager:
    """
    Manages strategy deployment lifecycle.

    Orchestrates package validation, deployment execution, canary
    rollouts, and rollback operations with full audit trail.

    Usage::

        dm = DeploymentManager(lifecycle_controller=lc, audit_center=audit)
        await dm.initialize()
        deployment = await dm.deploy(package, target)
    """

    def __init__(
        self,
        lifecycle_controller: Any = None,
        audit_center: Any = None,
    ) -> None:
        self._lifecycle_controller = lifecycle_controller
        self._audit_center = audit_center
        self._deployments: dict[str, DeploymentRecord] = {}
        self._deployment_counter: int = 0
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the deployment manager."""
        logger.info("DeploymentManager initialized.")

    async def stop(self) -> None:
        """Stop the deployment manager."""
        logger.info("DeploymentManager stopped.")

    # ---- Deployment Operations ----

    async def deploy(
        self,
        package: DeploymentPackage,
        target: Optional[DeploymentTarget] = None,
    ) -> DeploymentRecord:
        """Deploy a strategy package."""
        async with self._lock:
            self._deployment_counter += 1
            deployment_id = f"deploy_{self._deployment_counter:06d}"

            record = DeploymentRecord(
                deployment_id=deployment_id,
                strategy_id=package.strategy_id,
                version=package.version,
                target=target,
                status=DeploymentStatus.PENDING,
            )
            self._deployments[deployment_id] = record

        try:
            # Validate
            record.status = DeploymentStatus.VALIDATING
            record.stages.append({"stage": "validate", "status": "started", "timestamp": datetime.now(timezone.utc).isoformat()})
            await self._validate_package(package)
            record.status = DeploymentStatus.VALIDATED
            record.stages[-1]["status"] = "completed"

            # Deploy
            record.status = DeploymentStatus.DEPLOYING
            record.started_at = datetime.now(timezone.utc)
            record.stages.append({"stage": "deploy", "status": "started", "timestamp": datetime.now(timezone.utc).isoformat()})
            await self._execute_deployment(package, target)
            record.status = DeploymentStatus.DEPLOYED
            record.stages[-1]["status"] = "completed"

            # Lifecycle update
            if self._lifecycle_controller:
                from services.strategy.platform.lifecycle_controller import LifecycleAction
                await self._lifecycle_controller.transition(
                    package.strategy_id,
                    LifecycleAction.DEPLOY,
                    reason=f"Deployed version {package.version}",
                    metadata={"deployment_id": deployment_id},
                )

            record.status = DeploymentStatus.COMPLETED
            record.completed_at = datetime.now(timezone.utc)

            await self._audit("strategy.deploy", f"Deployed {package.strategy_id} v{package.version}")

        except Exception as e:
            logger.error(f"Deployment failed for {package.strategy_id}: {e}")
            record.status = DeploymentStatus.FAILED
            record.error = str(e)
            record.completed_at = datetime.now(timezone.utc)
            if record.stages:
                record.stages[-1]["status"] = "failed"
                record.stages[-1]["error"] = str(e)

        return record

    async def rollback(self, deployment_id: str) -> DeploymentRecord:
        """Rollback a deployment."""
        async with self._lock:
            record = self._deployments.get(deployment_id)
            if not record:
                raise ValueError(f"Deployment not found: {deployment_id}")
            if record.status not in (DeploymentStatus.DEPLOYED, DeploymentStatus.FAILED):
                raise ValueError(f"Cannot rollback from status: {record.status}")

        try:
            record.status = DeploymentStatus.ROLLED_BACK
            record.stages.append({"stage": "rollback", "status": "completed", "timestamp": datetime.now(timezone.utc).isoformat()})
            record.completed_at = datetime.now(timezone.utc)

            if self._lifecycle_controller:
                from services.strategy.platform.lifecycle_controller import LifecycleAction
                await self._lifecycle_controller.transition(
                    record.strategy_id,
                    LifecycleAction.ROLLBACK,
                    reason=f"Rolled back deployment {deployment_id}",
                )

            await self._audit("strategy.rollback", f"Rolled back {record.strategy_id}")

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            record.error = str(e)

        return record

    async def get_deployment(self, deployment_id: str) -> Optional[DeploymentRecord]:
        """Get a deployment record by ID."""
        return self._deployments.get(deployment_id)

    async def list_deployments(
        self,
        strategy_id: Optional[str] = None,
        status: Optional[DeploymentStatus] = None,
        limit: int = 100,
    ) -> list[DeploymentRecord]:
        """List deployments with optional filters."""
        results = list(self._deployments.values())
        if strategy_id:
            results = [d for d in results if d.strategy_id == strategy_id]
        if status:
            results = [d for d in results if d.status == status]
        return results[-limit:]

    async def cancel_deployment(self, deployment_id: str) -> DeploymentRecord:
        """Cancel a pending or in-progress deployment."""
        async with self._lock:
            record = self._deployments.get(deployment_id)
            if not record:
                raise ValueError(f"Deployment not found: {deployment_id}")
            if record.status in (DeploymentStatus.COMPLETED, DeploymentStatus.FAILED, DeploymentStatus.CANCELLED):
                raise ValueError(f"Cannot cancel deployment in status: {record.status}")

            record.status = DeploymentStatus.CANCELLED
            record.completed_at = datetime.now(timezone.utc)
            record.stages.append({"stage": "cancel", "status": "completed", "timestamp": datetime.now(timezone.utc).isoformat()})

        return record

    # ---- Internal ----

    async def _validate_package(self, package: DeploymentPackage) -> None:
        """Validate a deployment package."""
        if not package.strategy_id:
            raise ValueError("Package missing strategy_id")
        if not package.version:
            raise ValueError("Package missing version")
        logger.info(f"Package validated: {package.strategy_id} v{package.version}")

    async def _execute_deployment(
        self,
        package: DeploymentPackage,
        target: Optional[DeploymentTarget],
    ) -> None:
        """Execute the actual deployment."""
        await asyncio.sleep(0.01)  # Simulated deployment work
        logger.info(f"Deployment executed: {package.strategy_id} v{package.version}")

    async def _audit(self, category: str, message: str) -> None:
        if self._audit_center:
            try:
                await self._audit_center.record(category=category, message=message)
            except Exception as e:
                logger.error(f"Audit failed: {e}")
