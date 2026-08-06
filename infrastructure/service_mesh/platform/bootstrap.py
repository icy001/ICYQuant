"""Mesh Platform Bootstrap for the Service Mesh Platform.

Provides ``MeshPlatformBootstrap`` for ordered startup of all mesh
platform components: Configuration -> Service Discovery -> Control Plane
-> Runtime Container -> Plugin Manager -> Mesh Ready.
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

logger = logging.getLogger(__name__)


class PlatformBootstrapPhase(str, Enum):
    """Phases in the platform bootstrap sequence."""

    CONFIGURATION = "configuration"
    SERVICE_DISCOVERY = "service_discovery"
    CONTROL_PLANE = "control_plane"
    RUNTIME_CONTAINER = "runtime_container"
    PLUGIN_MANAGER = "plugin_manager"
    MESH_READY = "mesh_ready"


_BOOTSTRAP_ORDER = [
    PlatformBootstrapPhase.CONFIGURATION,
    PlatformBootstrapPhase.SERVICE_DISCOVERY,
    PlatformBootstrapPhase.CONTROL_PLANE,
    PlatformBootstrapPhase.RUNTIME_CONTAINER,
    PlatformBootstrapPhase.PLUGIN_MANAGER,
    PlatformBootstrapPhase.MESH_READY,
]

_PARALLEL_PHASES = {
    PlatformBootstrapPhase.CONFIGURATION,
    PlatformBootstrapPhase.SERVICE_DISCOVERY,
}


class MeshPlatformBootstrap:
    """Bootstrap manager for the service mesh platform."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._phases: Dict[PlatformBootstrapPhase, Callable] = {}
        self._phase_results: Dict[str, Any] = {}
        self._completed_phases: List[PlatformBootstrapPhase] = []
        self._failed_phase: Optional[PlatformBootstrapPhase] = None
        self._rolled_back = False
        self._startup_count = 0
        self._last_startup: Optional[Dict[str, Any]] = None
        self._dependency_graph: Dict[
            PlatformBootstrapPhase, List[PlatformBootstrapPhase]
        ] = {}

    def register_phase(
        self,
        phase: PlatformBootstrapPhase,
        init_fn: Callable,
        depends_on: Optional[List[PlatformBootstrapPhase]] = None,
    ) -> None:
        with self._lock:
            self._phases[phase] = init_fn
            if depends_on:
                self._dependency_graph[phase] = depends_on

    async def startup(
        self, timeout_s: float = 60.0
    ) -> Dict[str, Any]:
        """Execute platform bootstrap sequence."""
        with self._lock:
            self._startup_count += 1
            self._failed_phase = None
            self._rolled_back = False
            self._phase_results.clear()
            self._completed_phases.clear()

        start = time.monotonic()

        # Execute parallel phases first
        parallel_phases = [
            p for p in _BOOTSTRAP_ORDER if p in _PARALLEL_PHASES
        ]
        sequential_phases = [
            p for p in _BOOTSTRAP_ORDER if p not in _PARALLEL_PHASES
        ]

        # Run parallel phases
        if parallel_phases:
            try:
                await self._run_parallel_phases(
                    parallel_phases, timeout_s
                )
            except Exception as exc:
                phase = self._failed_phase
                logger.error(
                    "Parallel bootstrap failed: %s", exc
                )
                await self._rollback()
                return self._build_result(False, phase)

        # Run sequential phases
        for phase in sequential_phases:
            if time.monotonic() - start > timeout_s:
                self._failed_phase = phase
                logger.error(
                    "Bootstrap timeout at phase: %s", phase.value
                )
                await self._rollback()
                return self._build_result(False, phase)

            init_fn = self._phases.get(phase)
            if init_fn is None:
                self._phase_results[phase.value] = {
                    "success": True,
                    "skipped": True,
                }
                self._completed_phases.append(phase)
                continue

            # Check dependencies
            deps = self._dependency_graph.get(phase, [])
            for dep in deps:
                if dep not in self._completed_phases:
                    self._failed_phase = phase
                    logger.error(
                        "Dependency '%s' not met for phase '%s'",
                        dep.value,
                        phase.value,
                    )
                    await self._rollback()
                    return self._build_result(False, phase)

            try:
                phase_start = time.monotonic()
                result = init_fn()
                if asyncio.iscoroutine(result):
                    result = await asyncio.wait_for(
                        result, timeout=10.0
                    )
                duration = time.monotonic() - phase_start
                self._phase_results[phase.value] = {
                    "success": True,
                    "duration_s": duration,
                    "result": result,
                }
                self._completed_phases.append(phase)
                self._telemetry.log_bootstrap(
                    phase.value, "completed", duration
                )
                logger.info(
                    "Platform bootstrap phase '%s' completed in %.3fs.",
                    phase.value,
                    duration,
                )
            except Exception as exc:
                self._failed_phase = phase
                logger.error(
                    "Platform bootstrap phase '%s' failed: %s",
                    phase.value,
                    exc,
                )
                self._telemetry.log_bootstrap(
                    phase.value, "failed",
                    details={"error": str(exc)},
                )
                await self._rollback()
                return self._build_result(False, phase)

        result = self._build_result(True)
        self._last_startup = result

        logger.info(
            "Platform bootstrap completed: %d/%d phases in %.3fs.",
            len(self._completed_phases),
            len(_BOOTSTRAP_ORDER),
            time.monotonic() - start,
        )
        return result

    async def _run_parallel_phases(
        self,
        phases: List[PlatformBootstrapPhase],
        timeout_s: float,
    ) -> None:
        """Run multiple phases in parallel."""
        tasks: List[asyncio.Task] = []
        phase_map: Dict[asyncio.Task, PlatformBootstrapPhase] = {}

        for phase in phases:
            init_fn = self._phases.get(phase)
            if init_fn is None:
                self._phase_results[phase.value] = {
                    "success": True,
                    "skipped": True,
                }
                self._completed_phases.append(phase)
                continue

            task = asyncio.create_task(
                self._execute_phase(phase, init_fn)
            )
            tasks.append(task)
            phase_map[task] = phase

        if not tasks:
            return

        try:
            done, pending = await asyncio.wait(
                tasks, timeout=timeout_s,
                return_when=asyncio.ALL_COMPLETED,
            )

            for task in done:
                phase = phase_map.get(task)
                if phase is None:
                    continue
                try:
                    result = task.result()
                    if result.get("success"):
                        self._completed_phases.append(phase)
                        self._phase_results[phase.value] = result
                    else:
                        self._failed_phase = phase
                        raise RuntimeError(
                            f"Phase {phase.value} failed"
                        )
                except Exception as exc:
                    self._failed_phase = phase
                    raise

            for task in pending:
                task.cancel()

        except Exception:
            for task in tasks:
                if not task.done():
                    task.cancel()
            raise

    async def _execute_phase(
        self,
        phase: PlatformBootstrapPhase,
        init_fn: Callable,
    ) -> Dict[str, Any]:
        """Execute a single bootstrap phase."""
        phase_start = time.monotonic()
        result = init_fn()
        if asyncio.iscoroutine(result):
            result = await asyncio.wait_for(result, timeout=10.0)
        duration = time.monotonic() - phase_start
        return {
            "success": True,
            "duration_s": duration,
            "result": result,
        }

    async def _rollback(self) -> None:
        """Rollback completed phases in reverse order."""
        self._rolled_back = True
        logger.warning(
            "Rolling platform bootstrap back due to failure."
        )
        for phase in reversed(self._completed_phases):
            shutdown_fn = getattr(
                self._phases.get(phase),
                "shutdown",
                None,
            )
            if shutdown_fn:
                try:
                    result = shutdown_fn()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as exc:
                    logger.warning(
                        "Rollback of '%s' failed: %s",
                        phase.value,
                        exc,
                    )

    def _build_result(
        self,
        success: bool,
        failed_phase: Optional[PlatformBootstrapPhase] = None,
    ) -> Dict[str, Any]:
        return {
            "bootstrapped": success,
            "failed_phase": (
                failed_phase.value if failed_phase else None
            ),
            "completed_phases": [
                p.value for p in self._completed_phases
            ],
            "phase_results": dict(self._phase_results),
            "rollback_triggered": self._rolled_back,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "startup_count": self._startup_count,
                "registered_phases": [
                    p.value for p in self._phases.keys()
                ],
                "completed_phases": [
                    p.value for p in self._completed_phases
                ],
                "failed_phase": (
                    self._failed_phase.value
                    if self._failed_phase
                    else None
                ),
                "rolled_back": self._rolled_back,
                "last_startup": self._last_startup,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"MeshPlatformBootstrap(completed="
                f"{len(self._completed_phases)}/"
                f"{len(_BOOTSTRAP_ORDER)})"
            )
