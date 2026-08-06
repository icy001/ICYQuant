"""Rolling Upgrade Manager for the Service Mesh Platform.

Provides ``RollingUpgradeManager`` for zero-downtime upgrades
with canary deployment, health verification, traffic switching,
and automatic rollback.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics

logger = logging.getLogger(__name__)


class UpgradeState(str, Enum):
    """State of the upgrade process."""

    IDLE = "idle"
    CHECKING = "checking"
    CANARY_UPGRADING = "canary_upgrading"
    HEALTH_VERIFYING = "health_verifying"
    TRAFFIC_SWITCHING = "traffic_switching"
    ROLLBACK = "rollback"
    COMPLETED = "completed"
    FAILED = "failed"


class UpgradeStrategy(str, Enum):
    """Strategy for rolling upgrade."""

    CANARY = "canary"
    BLUE_GREEN = "blue_green"
    ROLLING = "rolling"
    RECREATE = "recreate"


class UpgradeOperation:
    """Represents an upgrade operation."""

    def __init__(
        self,
        operation_id: str,
        target_version: str,
        strategy: UpgradeStrategy = UpgradeStrategy.CANARY,
    ) -> None:
        self.operation_id = operation_id
        self.target_version = target_version
        self.strategy = strategy
        self.state = UpgradeState.CHECKING
        self.canary_percentage = 10
        self.canary_steps: List[int] = [10, 25, 50, 100]
        self.current_step = 0
        self.health_check_count = 0
        self.max_health_checks = 10
        self.errors: List[str] = []
        self.started_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None
        self.rollback_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "target_version": self.target_version,
            "strategy": self.strategy.value,
            "state": self.state.value,
            "status": self.state.value,
            "canary_percentage": self.canary_percentage,
            "current_step": self.current_step,
            "health_check_count": self.health_check_count,
            "errors": self.errors,
            "started_at": self.started_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat()
                if self.completed_at
                else None
            ),
        }


class RollingUpgradeManager:
    """Manages zero-downtime rolling upgrades."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._operations: Dict[str, UpgradeOperation] = {}
        self._health_check_fn: Optional[Callable] = None
        self._traffic_switch_fn: Optional[Callable] = None
        self._pre_upgrade_fn: Optional[Callable] = None
        self._post_upgrade_fn: Optional[Callable] = None
        self._rollback_fn: Optional[Callable] = None
        self._current_version = "0.4.0"
        self._next_id = 0
        self._max_operations = 20

    def _generate_id(self) -> str:
        self._next_id += 1
        return f"upgrade-{int(time.monotonic())}-{self._next_id}"

    def set_current_version(self, version: str) -> None:
        self._current_version = version

    def set_health_check_fn(
        self, fn: Callable
    ) -> None:
        self._health_check_fn = fn

    def set_traffic_switch_fn(
        self, fn: Callable
    ) -> None:
        self._traffic_switch_fn = fn

    def set_pre_upgrade_fn(
        self, fn: Callable
    ) -> None:
        self._pre_upgrade_fn = fn

    def set_post_upgrade_fn(
        self, fn: Callable
    ) -> None:
        self._post_upgrade_fn = fn

    def set_rollback_fn(
        self, fn: Callable
    ) -> None:
        self._rollback_fn = fn

    def _check_version(self) -> Dict[str, Any]:
        """Check if upgrade is possible."""
        return {
            "current_version": self._current_version,
            "can_upgrade": True,
        }

    async def start_upgrade(
        self,
        target_version: str,
        strategy: UpgradeStrategy = UpgradeStrategy.CANARY,
        canary_percentage: int = 10,
    ) -> Dict[str, Any]:
        """Start a rolling upgrade."""
        operation_id = self._generate_id()
        operation = UpgradeOperation(
            operation_id, target_version, strategy
        )
        operation.canary_percentage = canary_percentage

        # Pre-upgrade hook
        if self._pre_upgrade_fn:
            try:
                result = self._pre_upgrade_fn(target_version)
                if asyncio.iscoroutine(result):
                    result = await result
            except Exception as exc:
                return {
                    "success": False,
                    "error": f"Pre-upgrade failed: {exc}",
                }

        # Version check
        version_check = self._check_version()
        if not version_check.get("can_upgrade"):
            return {
                "success": False,
                "error": "Version check failed",
                "details": version_check,
            }

        self._add_operation(operation)

        self._telemetry.log_upgrade(
            target_version, "upgrade_started",
            {"operation_id": operation_id,
             "strategy": strategy.value},
        )

        # Execute upgrade based on strategy
        if strategy == UpgradeStrategy.CANARY:
            return await self._execute_canary_upgrade(operation)
        elif strategy == UpgradeStrategy.BLUE_GREEN:
            return await self._execute_blue_green_upgrade(operation)
        elif strategy == UpgradeStrategy.ROLLING:
            return await self._execute_rolling_upgrade(operation)
        else:
            return await self._execute_recreate_upgrade(operation)

    async def _execute_canary_upgrade(
        self, operation: UpgradeOperation
    ) -> Dict[str, Any]:
        """Execute canary upgrade."""
        steps = operation.canary_steps

        for i, percentage in enumerate(steps):
            operation.current_step = i

            # Canary phase
            operation.state = UpgradeState.CANARY_UPGRADING
            self._telemetry.log_upgrade(
                operation.target_version,
                "canary_upgrade",
                {"percentage": percentage},
            )

            # Health verification
            operation.state = UpgradeState.HEALTH_VERIFYING
            healthy = await self._verify_health(operation)

            if not healthy:
                # Rollback
                return await self._rollback(
                    operation, f"Health check failed at {percentage}%"
                )

            # Traffic switch
            operation.state = UpgradeState.TRAFFIC_SWITCHING
            await self._switch_traffic(operation, percentage)

        # Complete
        operation.state = UpgradeState.COMPLETED
        operation.completed_at = datetime.utcnow()
        self._current_version = operation.target_version

        # Post-upgrade hook
        if self._post_upgrade_fn:
            try:
                result = self._post_upgrade_fn(
                    operation.target_version
                )
                if asyncio.iscoroutine(result):
                    result = await result
            except Exception:
                pass

        self._metrics.increment_upgrade_total(
            {"strategy": "canary", "status": "completed"}
        )
        self._telemetry.log_upgrade(
            operation.target_version,
            "upgrade_completed",
            {"operation_id": operation.operation_id},
        )
        logger.info(
            "Upgrade '%s' completed successfully.",
            operation.operation_id,
        )
        return operation.to_dict()

    async def _execute_blue_green_upgrade(
        self, operation: UpgradeOperation
    ) -> Dict[str, Any]:
        """Execute blue-green upgrade."""
        operation.state = UpgradeState.CANARY_UPGRADING

        # Blue: health check
        healthy = await self._verify_health(operation)
        if not healthy:
            return await self._rollback(
                operation,
                "Health check failed during blue phase",
            )

        # Green: switch all traffic
        await self._switch_traffic(operation, 100)

        operation.state = UpgradeState.COMPLETED
        operation.completed_at = datetime.utcnow()
        self._current_version = operation.target_version

        self._metrics.increment_upgrade_total(
            {"strategy": "blue_green", "status": "completed"}
        )
        return operation.to_dict()

    async def _execute_rolling_upgrade(
        self, operation: UpgradeOperation
    ) -> Dict[str, Any]:
        """Execute rolling upgrade."""
        operation.state = UpgradeState.CANARY_UPGRADING

        # Step-by-step rolling
        steps = [25, 50, 75, 100]
        for percentage in steps:
            await self._switch_traffic(operation, percentage)
            healthy = await self._verify_health(operation)
            if not healthy:
                return await self._rollback(
                    operation,
                    f"Health check failed at {percentage}%",
                )

        operation.state = UpgradeState.COMPLETED
        operation.completed_at = datetime.utcnow()
        self._current_version = operation.target_version

        self._metrics.increment_upgrade_total(
            {"strategy": "rolling", "status": "completed"}
        )
        return operation.to_dict()

    async def _execute_recreate_upgrade(
        self, operation: UpgradeOperation
    ) -> Dict[str, Any]:
        """Execute recreate upgrade."""
        operation.state = UpgradeState.CANARY_UPGRADING

        healthy = await self._verify_health(operation)
        if not healthy:
            return await self._rollback(
                operation, "Health check failed"
            )

        operation.state = UpgradeState.COMPLETED
        operation.completed_at = datetime.utcnow()
        self._current_version = operation.target_version

        self._metrics.increment_upgrade_total(
            {"strategy": "recreate", "status": "completed"}
        )
        return operation.to_dict()

    async def _verify_health(
        self, operation: UpgradeOperation
    ) -> bool:
        """Verify health during upgrade."""
        if self._health_check_fn:
            for _ in range(operation.max_health_checks):
                operation.health_check_count += 1
                try:
                    result = self._health_check_fn()
                    if asyncio.iscoroutine(result):
                        result = await result
                    if result and result.get("healthy", True):
                        return True
                except Exception:
                    pass
                await asyncio.sleep(1.0)
            return False
        return True

    async def _switch_traffic(
        self,
        operation: UpgradeOperation,
        percentage: int,
    ) -> None:
        """Switch traffic to new version."""
        if self._traffic_switch_fn:
            try:
                result = self._traffic_switch_fn(percentage)
                if asyncio.iscoroutine(result):
                    result = await result
            except Exception:
                pass

    async def _rollback(
        self,
        operation: UpgradeOperation,
        reason: str,
    ) -> Dict[str, Any]:
        """Rollback upgrade."""
        operation.state = UpgradeState.ROLLBACK
        operation.rollback_count += 1
        operation.errors.append(reason)

        if self._rollback_fn:
            try:
                result = self._rollback_fn(reason)
                if asyncio.iscoroutine(result):
                    result = await result
            except Exception:
                pass

        self._metrics.increment_upgrade_total(
            {"status": "rollback"}
        )
        self._telemetry.log_upgrade(
            operation.target_version,
            "upgrade_rolled_back",
            {"operation_id": operation.operation_id,
             "reason": reason},
        )
        logger.warning(
            "Upgrade '%s' rolled back: %s",
            operation.operation_id,
            reason,
        )
        return {
            "success": False,
            "operation_id": operation.operation_id,
            "state": operation.state.value,
            "error": reason,
            "rollback_count": operation.rollback_count,
        }

    def _add_operation(self, operation: UpgradeOperation) -> None:
        with self._lock:
            self._operations[operation.operation_id] = operation
            if len(self._operations) > self._max_operations:
                oldest_id = next(iter(self._operations))
                self._operations.pop(oldest_id, None)

    def get_operation(
        self, operation_id: str
    ) -> Optional[UpgradeOperation]:
        return self._operations.get(operation_id)

    def list_operations(
        self,
        state: Optional[UpgradeState] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        operations = list(self._operations.values())
        if state:
            operations = [
                o for o in operations if o.state == state
            ]
        return [o.to_dict() for o in operations[-limit:]]

    async def rollback_upgrade(
        self, operation_id: str, reason: str = "manual"
    ) -> Dict[str, Any]:
        """Manually trigger rollback."""
        operation = self._operations.get(operation_id)
        if operation is None:
            return {
                "success": False,
                "error": "Operation not found",
            }
        return await self._rollback(operation, reason)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "current_version": self._current_version,
                "total_operations": len(self._operations),
                "by_state": self._count_by_state(),
                "rollback_count": sum(
                    o.rollback_count
                    for o in self._operations.values()
                ),
            }

    def _count_by_state(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for op in self._operations.values():
            state = op.state.value
            counts[state] = counts.get(state, 0) + 1
        return counts

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"RollingUpgradeManager("
                f"current={self._current_version}, "
                f"ops={len(self._operations)})"
            )
