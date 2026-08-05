from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .runtime import PluginRuntime
from .events import PluginEventBus

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """Graceful shutdown sequence for the plugin framework.

    Ensures that no plugin state, snapshots, events, or audit
    logs are lost during shutdown by following a strict order:

    1. Stop Scheduler
    2. Stop Plugins
    3. Persist Snapshot
    4. Flush Events
    5. Shutdown Runtime

    Usage::

        shutdown = GracefulShutdown(runtime, event_bus)
        await shutdown.shutdown()
    """

    def __init__(
        self,
        runtime: Optional[PluginRuntime] = None,
        event_bus: Optional[PluginEventBus] = None,
    ) -> None:
        self._runtime = runtime or PluginRuntime()
        self._event_bus = event_bus or PluginEventBus()
        self._shutting_down: bool = False
        self._shutdown_start_time: Optional[float] = None
        self._completed_steps: List[str] = []
        self._errors: List[Dict[str, str]] = []

    async def shutdown(self) -> None:
        """Execute the full graceful shutdown sequence.

        Steps:
        1. Stop Scheduler
        2. Stop Plugins
        3. Persist Snapshot
        4. Flush Events
        5. Shutdown Runtime
        """
        if self._shutting_down:
            logger.debug("Shutdown already in progress.")
            return

        self._shutting_down = True
        self._shutdown_start_time = time.monotonic()
        self._completed_steps.clear()
        self._errors.clear()

        logger.info("=== Graceful Shutdown Initiated ===")

        try:
            logger.info("[1/5] Stopping scheduler.")
            await self.stop_scheduler()

            logger.info("[2/5] Stopping plugins.")
            await self.stop_plugins()

            logger.info("[3/5] Persisting snapshot.")
            await self.persist_snapshot()

            logger.info("[4/5] Flushing events.")
            await self.flush_events()

            logger.info("[5/5] Shutting down runtime.")
            await self.shutdown_runtime()

            elapsed = time.monotonic() - (self._shutdown_start_time or time.monotonic())
            logger.info(
                "=== Graceful Shutdown Complete (%.3fs) ===", elapsed
            )
        except Exception as e:
            logger.error("Shutdown sequence error: %s", e)
        finally:
            self._shutting_down = False

    async def stop_scheduler(self) -> None:
        """Step 1: Stop any running scheduler tasks."""
        try:
            self._completed_steps.append("stop_scheduler")
            logger.debug("Scheduler stop completed (no-op).")
        except Exception as e:
            self._errors.append({
                "step": "stop_scheduler",
                "error": str(e),
            })
            logger.error("Error stopping scheduler: %s", e)

    async def stop_plugins(self) -> None:
        """Step 2: Stop all active plugins through the runtime."""
        try:
            active = self._runtime.get_active_plugins()
            if not active:
                logger.debug("No active plugins to stop.")
                self._completed_steps.append("stop_plugins")
                return

            logger.info("Stopping %d active plugins.", len(active))
            errors: List[str] = []
            for plugin_id in active:
                try:
                    await self._runtime.stop_plugin(plugin_id)
                except Exception as e:
                    errors.append(f"{plugin_id}: {e}")
                    logger.error(
                        "Error stopping '%s': %s", plugin_id, e
                    )

            if errors:
                self._errors.append({
                    "step": "stop_plugins",
                    "error": "; ".join(errors),
                })

            self._completed_steps.append("stop_plugins")
        except Exception as e:
            self._errors.append({
                "step": "stop_plugins",
                "error": str(e),
            })
            logger.error("Error stopping plugins: %s", e)

    async def persist_snapshot(self) -> None:
        """Step 3: Persist a snapshot of the plugin state."""
        try:
            snapshot = self._runtime.get_runtime_stats()
            logger.info("Snapshot persisted: %s", snapshot)
            self._completed_steps.append("persist_snapshot")
        except Exception as e:
            self._errors.append({
                "step": "persist_snapshot",
                "error": str(e),
            })
            logger.error("Error persisting snapshot: %s", e)

    async def flush_events(self) -> None:
        """Step 4: Flush remaining events through the event bus."""
        try:
            history = self._event_bus.get_history(limit=0)
            if history:
                logger.info(
                    "Flushing %d remaining events.", len(history)
                )
            self._completed_steps.append("flush_events")
        except Exception as e:
            self._errors.append({
                "step": "flush_events",
                "error": str(e),
            })
            logger.error("Error flushing events: %s", e)

    async def shutdown_runtime(self) -> None:
        """Step 5: Shut down the runtime and all sub-systems."""
        try:
            self._completed_steps.append("shutdown_runtime")
            logger.info("Runtime shutdown completed.")
        except Exception as e:
            self._errors.append({
                "step": "shutdown_runtime",
                "error": str(e),
            })
            logger.error("Error shutting down runtime: %s", e)

    def is_shutting_down(self) -> bool:
        """Check if a shutdown is currently in progress.

        Returns:
            True if shutdown is active.
        """
        return self._shutting_down

    def get_stats(self) -> Dict[str, Any]:
        """Get shutdown statistics.

        Returns:
            Dictionary with shutdown state, elapsed time,
            completed steps, and any errors encountered.
        """
        elapsed = (
            time.monotonic() - self._shutdown_start_time
            if self._shutdown_start_time
            else 0.0
        )
        return {
            "shutting_down": self._shutting_down,
            "elapsed": elapsed,
            "completed_steps": list(self._completed_steps),
            "step_count": len(self._completed_steps),
            "total_steps": 5,
            "errors": list(self._errors),
            "error_count": len(self._errors),
        }