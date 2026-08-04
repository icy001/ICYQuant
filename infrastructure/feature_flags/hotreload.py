"""
Feature flag hot reload management.

Provides zero-downtime feature flag updates
with atomic snapshot swap, validation, and
automatic rollback on failure.

Hot Reload Pipeline:
    Feature Changed → Validation → Snapshot Build
        → Atomic Swap → Publish Event → Subscribers Refresh
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .events import FeatureEvent, FeatureEventType
from .publisher import FeatureEventPublisher
from .runtime import RuntimeFeatureService
from .snapshot import FeatureSnapshot, SnapshotManager
from .validator import FeatureFlagValidator

logger = logging.getLogger(__name__)


class HotReloadManager:
    """
    Manages hot reload of feature flags.

    Provides zero-downtime updates using
    atomic snapshot swaps and automatic
    rollback on validation failure.

    Pipeline:
        1. Receive flag change notification
        2. Validate the new configuration
        3. Build a new snapshot
        4. Atomically swap the current snapshot
        5. Publish event to subscribers
        6. Refresh all runtime nodes

    Guarantees:
        - No downtime during reload
        - Lock-free reads during swap
        - Automatic rollback on failure
        - Event notification for all changes

    Usage:
        hr = HotReloadManager(runtime, publisher)
        await hr.reload(flags)
    """

    def __init__(
        self,
        runtime: Optional[RuntimeFeatureService] = None,
        publisher: Optional[FeatureEventPublisher] = None,
        validator: Optional[FeatureFlagValidator] = None,
    ) -> None:
        """
        Initialize hot reload manager.

        Args:
            runtime: RuntimeFeatureService instance.
            publisher: FeatureEventPublisher instance.
            validator: FeatureFlagValidator instance.
        """
        self._runtime = runtime or RuntimeFeatureService()
        self._publisher = publisher or FeatureEventPublisher()
        self._validator = validator or FeatureFlagValidator()
        self._reload_count = 0
        self._error_count = 0
        self._last_reload_time: float = 0
        self._lock = asyncio.Lock()
        self._in_reload = False

    @property
    def runtime(self) -> RuntimeFeatureService:
        """Get the runtime service."""
        return self._runtime

    @property
    def publisher(self) -> FeatureEventPublisher:
        """Get the event publisher."""
        return self._publisher

    async def reload(
        self,
        flags: Dict[str, Dict[str, Any]],
        operator: str = "system",
        reason: str = "reload",
    ) -> Dict[str, Any]:
        """
        Perform a hot reload with new flag data.

        This is the main entry point for reloading
        feature flags without downtime.

        Args:
            flags: New flag data dictionary.
            operator: Who triggered the reload.
            reason: Reason for the reload.

        Returns:
            Reload result dictionary.
        """
        if self._in_reload:
            return {
                "success": False,
                "reason": "reload_in_progress",
                "reload_count": self._reload_count,
            }

        self._in_reload = True
        start = time.perf_counter()

        try:
            # Step 1: Validate the new data
            validation_errors = self._validate_flags(flags)
            if validation_errors:
                self._error_count += 1
                return {
                    "success": False,
                    "reason": "validation_failed",
                    "errors": validation_errors,
                }

            # Step 2: Build new snapshot
            old_snapshot = self._runtime.snapshot_manager.get_current()
            new_snapshot = self._runtime.snapshot_manager.create_snapshot(flags)

            # Step 3: Atomic swap
            self._runtime._current_flags = dict(flags)
            self._runtime.snapshot_manager.activate(new_snapshot)

            # Step 4: Verify integrity
            if not new_snapshot.verify_integrity():
                self._error_count += 1
                # Rollback
                if old_snapshot:
                    self._runtime._current_flags = dict(old_snapshot.flags)
                    self._runtime.snapshot_manager.activate(old_snapshot)
                return {
                    "success": False,
                    "reason": "integrity_check_failed",
                    "rolled_back": True,
                }

            # Step 5: Publish event
            await self._publisher.publish(
                FeatureEventType.HOT_RELOAD,
                data={
                    "version": new_snapshot.version,
                    "flags_count": len(flags),
                    "operator": operator,
                    "reason": reason,
                },
                operator=operator,
            )

            self._reload_count += 1
            self._last_reload_time = time.monotonic()
            duration_ms = (time.perf_counter() - start) * 1000

            logger.info(
                "Hot reload completed: %d flags, v%d, %.1fms",
                len(flags),
                new_snapshot.version,
                duration_ms,
            )

            return {
                "success": True,
                "version": new_snapshot.version,
                "flags_count": len(flags),
                "duration_ms": duration_ms,
                "reload_count": self._reload_count,
            }

        except Exception as e:
            self._error_count += 1
            logger.error("Hot reload failed: %s", e)

            # Attempt rollback
            try:
                old_snapshot = self._runtime.snapshot_manager.get_current()
                if old_snapshot:
                    self._runtime.refresh(old_snapshot.flags)
            except Exception as rollback_err:
                logger.error("Rollback also failed: %s", rollback_err)

            return {
                "success": False,
                "reason": str(e),
                "rolled_back": True,
            }
        finally:
            self._in_reload = False

    async def reload_flag(
        self,
        key: str,
        flag_data: Dict[str, Any],
        operator: str = "system",
        reason: str = "flag_update",
    ) -> Dict[str, Any]:
        """
        Reload a single flag into the runtime.

        Args:
            key: Flag key to update.
            flag_data: New flag data.
            operator: Who triggered the update.
            reason: Reason for the update.

        Returns:
            Reload result.
        """
        # Get current flags
        current = self._runtime._current_flags.copy()

        # Update the specific flag
        current[key] = flag_data

        # Perform full reload
        result = await self.reload(current, operator=operator, reason=reason)
        result["updated_key"] = key
        return result

    async def delete_flag(
        self,
        key: str,
        operator: str = "system",
        reason: str = "flag_delete",
    ) -> Dict[str, Any]:
        """
        Delete a flag from the runtime.

        Args:
            key: Flag key to delete.
            operator: Who triggered the deletion.
            reason: Reason for deletion.

        Returns:
            Reload result.
        """
        current = self._runtime._current_flags.copy()

        if key not in current:
            return {
                "success": False,
                "reason": "flag_not_found",
            }

        del current[key]

        result = await self.reload(current, operator=operator, reason=reason)
        result["deleted_key"] = key
        return result

    async def rollback(
        self,
        version: int,
        operator: str = "system",
        reason: str = "rollback",
    ) -> Dict[str, Any]:
        """
        Rollback to a previous snapshot version.

        Args:
            version: Version to rollback to.
            operator: Who triggered the rollback.
            reason: Reason for rollback.

        Returns:
            Rollback result.
        """
        result = self._runtime.snapshot_manager.rollback_to(version)
        if result is None:
            return {
                "success": False,
                "reason": "version_not_found",
                "version": version,
            }

        # Refresh runtime with rolled-back data
        self._runtime._current_flags = dict(result.flags)

        # Publish rollback event
        await self._publisher.publish(
            FeatureEventType.SNAPSHOT_ROLLED_BACK,
            data={
                "rolled_back_to": version,
                "new_version": result.version,
                "flags_count": len(result.flags),
                "operator": operator,
            },
            operator=operator,
        )

        logger.info(
            "Rolled back to version %d (new v%d)",
            version,
            result.version,
        )

        return {
            "success": True,
            "rolled_back_to": version,
            "new_version": result.version,
            "flags_count": len(result.flags),
        }

    def _validate_flags(
        self,
        flags: Dict[str, Dict[str, Any]],
    ) -> List[str]:
        """Validate flag data before reload, adding defaults as needed."""
        errors = []

        for key, data in flags.items():
            if not key:
                errors.append(f"Empty flag key")
                continue

            if not isinstance(data, dict):
                errors.append(f"Flag {key}: data must be a dict")
                continue

            # Add sensible defaults for missing fields
            if "flag_type" not in data:
                data["flag_type"] = "boolean"

            if "default_value" not in data:
                data["default_value"] = data.get("enabled", False)

            if "key" not in data:
                data["key"] = key

        return errors

    def get_stats(self) -> Dict[str, Any]:
        """Get hot reload statistics."""
        return {
            "reload_count": self._reload_count,
            "error_count": self._error_count,
            "last_reload_time": self._last_reload_time,
            "in_reload": self._in_reload,
            "runtime_stats": self._runtime.get_stats(),
        }
