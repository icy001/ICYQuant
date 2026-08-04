"""
Feature flag platform automatic recovery.

Provides automatic recovery mechanisms
when the runtime encounters failures:
    - Snapshot restoration
    - Cache refresh
    - Service resumption
    - Health verification
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .hotreload import HotReloadManager
from .runtime import RuntimeFeatureService
from .snapshot import FeatureSnapshot, SnapshotManager

logger = logging.getLogger(__name__)


class RecoveryManager:
    """
    Manages automatic recovery of the feature flag platform.

    When runtime failures occur, the recovery manager:
        1. Detects the failure
        2. Restores the last known good snapshot
        3. Refreshes all caches
        4. Verifies health
        5. Resumes service

    Recovery Flow:
        Runtime Failure → Detect → Restore Snapshot
            → Refresh Cache → Verify Health → Resume Service

    Usage:
        recovery = RecoveryManager(hot_reload, runtime)
        result = await recovery.recover("runtime_error")
    """

    def __init__(
        self,
        hot_reload: Optional[HotReloadManager] = None,
        runtime: Optional[RuntimeFeatureService] = None,
    ) -> None:
        """
        Initialize recovery manager.

        Args:
            hot_reload: HotReloadManager instance.
            runtime: RuntimeFeatureService instance.
        """
        self._hot_reload = hot_reload or HotReloadManager()
        self._runtime = runtime or self._hot_reload.runtime
        self._recovery_count = 0
        self._last_recovery_time: float = 0
        self._last_recovery_reason = ""
        self._recovery_history: List[Dict[str, Any]] = []

    async def recover(
        self,
        reason: str = "runtime_failure",
        operator: str = "system",
    ) -> Dict[str, Any]:
        """
        Perform automatic recovery.

        Args:
            reason: Reason for recovery.
            operator: Who triggered recovery.

        Returns:
            Recovery result.
        """
        self._recovery_count += 1
        self._last_recovery_reason = reason

        logger.warning(
            "Starting recovery: reason=%s, recovery_count=%d",
            reason,
            self._recovery_count,
        )

        steps = []

        # Step 1: Restore last known good snapshot
        restore_result = await self._restore_snapshot()
        steps.append({
            "step": "restore_snapshot",
            "success": restore_result.get("success", False),
            "details": restore_result,
        })

        if not restore_result.get("success", False):
            return {
                "success": False,
                "reason": "snapshot_restore_failed",
                "steps": steps,
                "recovery_count": self._recovery_count,
            }

        # Step 2: Refresh caches
        refresh_result = await self._refresh_caches()
        steps.append({
            "step": "refresh_caches",
            "success": refresh_result.get("success", False),
            "details": refresh_result,
        })

        # Step 3: Verify health
        health_result = await self._verify_health()
        steps.append({
            "step": "verify_health",
            "success": health_result.get("healthy", False),
            "details": health_result,
        })

        # Step 4: Resume service
        resume_result = await self._resume_service()
        steps.append({
            "step": "resume_service",
            "success": resume_result.get("success", False),
            "details": resume_result,
        })

        # Determine overall success
        all_steps_ok = all(s["success"] for s in steps)

        result = {
            "success": all_steps_ok,
            "reason": reason,
            "steps": steps,
            "recovery_count": self._recovery_count,
        }

        self._recovery_history.append(result)

        if all_steps_ok:
            logger.info(
                "Recovery completed successfully (count=%d)",
                self._recovery_count,
            )
        else:
            logger.error(
                "Recovery failed: %s",
                [s for s in steps if not s["success"]],
            )

        return result

    async def _restore_snapshot(self) -> Dict[str, Any]:
        """Restore the last known good snapshot."""
        try:
            mgr = self._runtime.snapshot_manager

            # Try current snapshot first
            current = mgr.get_current()
            if current and current.flags:
                # Verify integrity
                if current.verify_integrity():
                    self._runtime._current_flags = dict(current.flags)
                    mgr.activate(current)
                    return {
                        "success": True,
                        "source": "current",
                        "version": current.version,
                    }

            # Try history
            history = mgr.get_history(limit=5)
            for snap in reversed(history):
                if snap.flags and snap.verify_integrity():
                    self._runtime._current_flags = dict(snap.flags)
                    mgr.activate(snap)
                    return {
                        "success": True,
                        "source": "history",
                        "version": snap.version,
                    }

            # Create empty snapshot as last resort
            empty_snap = mgr.create_snapshot({})
            mgr.activate(empty_snap)
            return {
                "success": True,
                "source": "empty",
                "version": empty_snap.version,
                "warning": "no_valid_snapshot_found",
            }

        except Exception as e:
            logger.error("Snapshot restore failed: %s", e)
            return {
                "success": False,
                "reason": str(e),
            }

    async def _refresh_caches(self) -> Dict[str, Any]:
        """Refresh all caches in the runtime."""
        try:
            # The runtime's _current_flags dict is already updated
            # by _restore_snapshot. We just need to reset stats.
            self._runtime.reset_stats()

            # Reset cache if available
            if hasattr(self._runtime, '_cache') and self._runtime._cache:
                self._runtime._cache.clear()

            return {"success": True}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    async def _verify_health(self) -> Dict[str, Any]:
        """Verify the health of the recovered runtime."""
        try:
            stats = self._runtime.get_stats()
            is_running = stats.get("running", False)
            flags_count = stats.get("flags_count", 0)

            # Consider healthy if flags are loaded, even if not yet started
            healthy = flags_count > 0 or is_running

            return {
                "healthy": healthy,
                "is_running": is_running,
                "flags_count": flags_count,
            }
        except Exception as e:
            return {"healthy": False, "reason": str(e)}

    async def _resume_service(self) -> Dict[str, Any]:
        """Resume the runtime service."""
        try:
            if not self._runtime.is_running:
                await self._runtime.start()
            return {"success": True}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """Get recovery manager statistics."""
        return {
            "recovery_count": self._recovery_count,
            "last_recovery_time": self._last_recovery_time,
            "last_recovery_reason": self._last_recovery_reason,
            "history_length": len(self._recovery_history),
            "runtime_stats": self._runtime.get_stats(),
        }
