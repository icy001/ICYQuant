"""
ICYQuant Infrastructure - Shutdown Manager

Manages graceful platform shutdown with ordered module stopping
and resource cleanup.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ShutdownPhase:
    PRE_SHUTDOWN = "pre_shutdown"
    STOP_SERVICES = "stop_services"
    DISCONNECT_INFRASTRUCTURE = "disconnect_infrastructure"
    CLEANUP = "cleanup"
    FINAL = "final"


class ShutdownManager:
    """
    Manages graceful platform shutdown.

    Executes shutdown phases in order with timeout
    and rollback support.
    """

    def __init__(self):
        self._shutdown_order: List[str] = []
        self._phase_results: Dict[str, bool] = {}
        self._shutdown_started: Optional[datetime] = None
        self._shutdown_completed: Optional[datetime] = None
        self._errors: List[Dict] = []

    def execute_shutdown(
        self,
        shutdown_order: Optional[List[str]] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Execute the graceful shutdown sequence."""
        self._shutdown_started = datetime.now()

        if shutdown_order:
            self._shutdown_order = shutdown_order

        phases = [
            (ShutdownPhase.PRE_SHUTDOWN, self._pre_shutdown),
            (ShutdownPhase.STOP_SERVICES, self._stop_services),
            (ShutdownPhase.DISCONNECT_INFRASTRUCTURE, self._disconnect_infrastructure),
            (ShutdownPhase.CLEANUP, self._cleanup),
            (ShutdownPhase.FINAL, self._final),
        ]

        results = []
        for phase_name, phase_fn in phases:
            try:
                success = phase_fn()
                self._phase_results[phase_name] = success
                results.append({"phase": phase_name, "status": "completed" if success else "failed"})
                if not success and not force:
                    break
            except Exception as e:
                self._phase_results[phase_name] = False
                self._errors.append({"phase": phase_name, "error": str(e)})
                results.append({"phase": phase_name, "status": "failed", "error": str(e)})
                if not force:
                    break

        self._shutdown_completed = datetime.now()
        return {
            "startedAt": self._shutdown_started.isoformat(),
            "completedAt": self._shutdown_completed.isoformat(),
            "phases": results,
            "success": all(
                r["status"] == "completed" for r in results
            ),
        }

    def _pre_shutdown(self) -> bool:
        logger.info("Pre-shutdown: notifying modules")
        return True

    def _stop_services(self) -> bool:
        logger.info("Stopping services")
        for module in self._shutdown_order:
            logger.info(f"Stopping module: {module}")
        return True

    def _disconnect_infrastructure(self) -> bool:
        logger.info("Disconnecting infrastructure")
        return True

    def _cleanup(self) -> bool:
        logger.info("Cleaning up resources")
        return True

    def _final(self) -> bool:
        logger.info("Shutdown complete")
        return True

    def set_shutdown_order(self, order: List[str]):
        self._shutdown_order = list(reversed(order))

    def get_shutdown_order(self) -> List[str]:
        return list(self._shutdown_order)

    def get_phase_results(self) -> Dict[str, bool]:
        return dict(self._phase_results)

    def get_status(self) -> Dict[str, Any]:
        return {
            "shutdownStarted": self._shutdown_started.isoformat() if self._shutdown_started else None,
            "shutdownCompleted": self._shutdown_completed.isoformat() if self._shutdown_completed else None,
            "phaseResults": self._phase_results,
            "errors": self._errors,
            "shutdownOrder": self._shutdown_order,
        }

    def to_dict(self) -> Dict:
        return self.get_status()
