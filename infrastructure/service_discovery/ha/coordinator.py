"""HA controller for ICYQuant service discovery HA.

Provides ``HAController`` for orchestrating the full HA pipeline:
Heartbeat -> Failure Detector -> Failover -> Recovery -> Rebalance.

Coordinates all HA sub-components into a unified control plane.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HAController:
    """Orchestrates the HA pipeline across all sub-components.

    Coordinates:
        Heartbeat -> Failure Detector -> Failover -> Recovery -> Rebalance

    Acts as a central control plane that ties together failover
    managers, self-healing engines, snapshots, and rebalancers.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._components: Dict[str, Any] = {}
        self._coordinate_count = 0
        self._rebalance_count = 0
        self._recover_count = 0
        self._last_coordinate: Optional[Dict[str, Any]] = None
        self._last_rebalance: Optional[Dict[str, Any]] = None
        self._last_recover: Optional[Dict[str, Any]] = None
        self._history: List[Dict[str, Any]] = []
        self._max_history = 200

    # ── Helpers ──

    @staticmethod
    def _now_iso() -> str:
        return datetime.utcnow().isoformat()

    # ── Component management ──

    def register_component(self, name: str, component: Any) -> None:
        """Register a component with the controller.

        Args:
            name: Unique component name.
            component: The component instance.
        """
        if not name:
            raise ValueError("name cannot be empty.")
        with self._lock:
            self._components[name] = component
        logger.debug("Registered component '%s'.", name)

    def get_component(self, name: str) -> Any:
        """Retrieve a registered component by name.

        Args:
            name: The component name.

        Returns:
            The component instance, or None if not found.
        """
        with self._lock:
            return self._components.get(name)

    # ── Public API ──

    async def coordinate(self) -> Dict[str, Any]:
        """Orchestrate the full HA pipeline.

        Executes heartbeat checks, failure detection, failover,
        recovery, and rebalance in sequence.

        Returns:
            A dictionary describing the pipeline execution result.
        """
        with self._lock:
            self._coordinate_count += 1

        result: Dict[str, Any] = {
            "coordinated": True,
            "stages": {},
            "timestamp": self._now_iso(),
        }

        result["stages"]["heartbeat"] = await self._run_heartbeat()
        result["stages"]["failure_detection"] = (
            await self._run_failure_detection()
        )
        result["stages"]["failover"] = await self._run_failover()
        result["stages"]["recovery"] = await self._run_recovery()
        result["stages"]["rebalance"] = await self._run_rebalance()

        with self._lock:
            self._last_coordinate = result

        self._record_history("coordinate", result)

        all_ok = all(
            stage.get("ok", stage.get("success", True)) is not False
            for stage in result["stages"].values()
            if isinstance(stage, dict)
        )

        if all_ok:
            logger.info("HA pipeline completed successfully.")
        else:
            logger.warning("HA pipeline completed with issues.")

        return result

    async def rebalance(self) -> Dict[str, Any]:
        """Trigger cluster rebalancing.

        Returns:
            A dictionary describing the rebalance result.
        """
        with self._lock:
            self._rebalance_count += 1

        result: Dict[str, Any] = {
            "rebalanced": True,
            "timestamp": self._now_iso(),
        }

        rebalancer = self._components.get("rebalancer")
        if rebalancer is not None:
            rebalance_func = getattr(rebalancer, "rebalance", None)
            if callable(rebalance_func):
                try:
                    coro = rebalance_func()
                    if asyncio.iscoroutine(coro):
                        rebalance_result = await coro
                    else:
                        rebalance_result = coro
                    result["rebalancer_result"] = rebalance_result
                except Exception as exc:
                    logger.warning("Rebalance failed: %s", exc)
                    result["rebalanced"] = False
                    result["error"] = str(exc)
            else:
                result["note"] = "rebalancer has no rebalance method"
        else:
            result["note"] = "no_rebalancer_registered"

        with self._lock:
            self._last_rebalance = result

        self._record_history("rebalance", result)
        logger.info("Cluster rebalance triggered.")
        return result

    async def recover(self) -> Dict[str, Any]:
        """Trigger recovery for failed components.

        Returns:
            A dictionary describing the recovery result.
        """
        with self._lock:
            self._recover_count += 1

        result: Dict[str, Any] = {
            "recovered": True,
            "timestamp": self._now_iso(),
        }

        recovery = self._components.get("recovery")
        if recovery is not None:
            recover_func = getattr(recovery, "resume", None)
            if callable(recover_func):
                try:
                    coro = recover_func()
                    if asyncio.iscoroutine(coro):
                        recovery_result = await coro
                    else:
                        recovery_result = coro
                    result["recovery_result"] = recovery_result
                except Exception as exc:
                    logger.warning("Recovery failed: %s", exc)
                    result["recovered"] = False
                    result["error"] = str(exc)
            else:
                result["note"] = "recovery has no resume method"
        else:
            result["note"] = "no_recovery_registered"

        self_healing = self._components.get("self_healing")
        if self_healing is not None:
            verify_func = getattr(self_healing, "verify", None)
            if callable(verify_func):
                try:
                    coro = verify_func("*")
                    if asyncio.iscoroutine(coro):
                        verified = await coro
                    else:
                        verified = coro
                    result["verified"] = bool(verified)
                except Exception as exc:
                    logger.warning("Verification failed: %s", exc)
                    result["verified"] = False

        with self._lock:
            self._last_recover = result

        self._record_history("recover", result)
        logger.info("Recovery triggered.")
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the HA controller."""
        with self._lock:
            return {
                "coordinate_count": self._coordinate_count,
                "rebalance_count": self._rebalance_count,
                "recover_count": self._recover_count,
                "components": sorted(self._components.keys()),
                "last_coordinate": (
                    {
                        "timestamp": (
                            self._last_coordinate.get("timestamp")
                            if self._last_coordinate
                            else None
                        ),
                    }
                    if self._last_coordinate
                    else None
                ),
                "last_rebalance": (
                    {
                        "timestamp": (
                            self._last_rebalance.get("timestamp")
                            if self._last_rebalance
                            else None
                        ),
                    }
                    if self._last_rebalance
                    else None
                ),
                "last_recover": (
                    {
                        "timestamp": (
                            self._last_recover.get("timestamp")
                            if self._last_recover
                            else None
                        ),
                    }
                    if self._last_recover
                    else None
                ),
                "history_size": len(self._history),
                "max_history": self._max_history,
            }

    # ── Pipeline stages ──

    async def _run_heartbeat(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"ok": True, "checked": 0}
        for name, comp in self._components.items():
            hb_func = getattr(comp, "heartbeat", None)
            if callable(hb_func):
                try:
                    coro = hb_func()
                    if asyncio.iscoroutine(coro):
                        await coro
                    result["checked"] += 1
                except Exception as exc:
                    logger.warning(
                        "Heartbeat failed for '%s': %s", name, exc
                    )
                    result["ok"] = False
        return result

    async def _run_failure_detection(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"ok": True, "detected": 0}
        detector = self._components.get("failure_detector")
        if detector is not None:
            detect_func = getattr(detector, "detect", None)
            if callable(detect_func):
                try:
                    coro = detect_func()
                    if asyncio.iscoroutine(coro):
                        det_result = await coro
                    else:
                        det_result = coro
                    if isinstance(det_result, dict):
                        result["detected"] = int(
                            det_result.get("failures_detected", 0)
                        )
                        result["ok"] = not bool(
                            det_result.get("failures_detected", 0)
                        )
                except Exception as exc:
                    logger.warning(
                        "Failure detection failed: %s", exc
                    )
                    result["ok"] = False
        return result

    async def _run_failover(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"ok": True, "failover_executed": False}
        failover_mgr = self._components.get("failover")
        if failover_mgr is not None:
            fo_func = getattr(failover_mgr, "execute_failover", None)
            if callable(fo_func):
                try:
                    coro = fo_func()
                    if asyncio.iscoroutine(coro):
                        fo_result = await coro
                    else:
                        fo_result = coro
                    if isinstance(fo_result, dict):
                        result["ok"] = fo_result.get(
                            "failover_executed", True
                        )
                        result["failover_executed"] = fo_result.get(
                            "failover_executed", False
                        )
                except Exception as exc:
                    logger.warning("Failover failed: %s", exc)
                    result["ok"] = False
        return result

    async def _run_recovery(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"ok": True, "recovered": 0}
        recovery = self._components.get("recovery")
        if recovery is not None:
            resume_func = getattr(recovery, "resume", None)
            if callable(resume_func):
                try:
                    coro = resume_func()
                    if asyncio.iscoroutine(coro):
                        rec_result = await coro
                    else:
                        rec_result = coro
                    if isinstance(rec_result, dict):
                        result["ok"] = rec_result.get("resumed", True)
                except Exception as exc:
                    logger.warning("Recovery failed: %s", exc)
                    result["ok"] = False
        return result

    async def _run_rebalance(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"ok": True, "rebalanced": False}
        rebalancer = self._components.get("rebalancer")
        if rebalancer is not None:
            rb_func = getattr(rebalancer, "rebalance", None)
            if callable(rb_func):
                try:
                    coro = rb_func()
                    if asyncio.iscoroutine(coro):
                        rb_result = await coro
                    else:
                        rb_result = coro
                    if isinstance(rb_result, dict):
                        result["ok"] = rb_result.get("rebalanced", True)
                        result["rebalanced"] = rb_result.get(
                            "rebalanced", False
                        )
                except Exception as exc:
                    logger.warning("Rebalance failed: %s", exc)
                    result["ok"] = False
        return result

    # ── Internal ──

    def _record_history(self, event: str, data: Dict[str, Any]) -> None:
        self._history.append(
            {"event": event, "data": data, "recorded_at": time.time()}
        )
        if len(self._history) > self._max_history:
            excess = len(self._history) - self._max_history
            del self._history[:excess]

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"HAController(components={len(self._components)}, "
                f"coordinates={self._coordinate_count})"
            )