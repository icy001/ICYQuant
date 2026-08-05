"""Mesh Bootstrap for the Service Mesh.

Provides ``MeshBootstrap`` for ordered startup of all mesh
components: Configuration -> Service Discovery -> Control Plane
-> Data Plane -> Sidecar Runtime -> Mesh Ready.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .context import MeshContext
from .events import MeshEvent, MeshEventPublisher
from .lifecycle import MeshLifecycle, MeshState
from .exceptions import MeshBootstrapError

logger = logging.getLogger(__name__)


class BootstrapPhase(str, Enum):
    """Phases in the mesh bootstrap sequence."""

    CONFIGURATION = "configuration"
    SERVICE_DISCOVERY = "service_discovery"
    CONTROL_PLANE = "control_plane"
    DATA_PLANE = "data_plane"
    SIDECAR_RUNTIME = "sidecar_runtime"
    MESH_READY = "mesh_ready"


_BOOTSTRAP_ORDER = [
    BootstrapPhase.CONFIGURATION,
    BootstrapPhase.SERVICE_DISCOVERY,
    BootstrapPhase.CONTROL_PLANE,
    BootstrapPhase.DATA_PLANE,
    BootstrapPhase.SIDECAR_RUNTIME,
    BootstrapPhase.MESH_READY,
]


class MeshBootstrap:
    """Bootstrap manager for the service mesh."""

    def __init__(
        self,
        context: Optional[MeshContext] = None,
        lifecycle: Optional[MeshLifecycle] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context or MeshContext()
        self._lifecycle = lifecycle or MeshLifecycle()
        self._phases: Dict[BootstrapPhase, Callable] = {}
        self._phase_results: Dict[str, Any] = {}
        self._completed_phases: List[BootstrapPhase] = []
        self._failed_phase: Optional[BootstrapPhase] = None
        self._rolled_back = False
        self._publisher: Optional[MeshEventPublisher] = None
        self._startup_count = 0
        self._last_startup: Optional[Dict[str, Any]] = None

    def set_publisher(self, publisher: MeshEventPublisher) -> None:
        self._publisher = publisher

    def register_phase(
        self,
        phase: BootstrapPhase,
        init_fn: Callable,
    ) -> None:
        with self._lock:
            self._phases[phase] = init_fn

    async def startup(
        self, timeout_s: float = 60.0
    ) -> Dict[str, Any]:
        """Execute bootstrap sequence."""
        with self._lock:
            self._startup_count += 1
            self._failed_phase = None
            self._rolled_back = False
            self._phase_results.clear()
            self._completed_phases.clear()

        self._lifecycle.transition_to(
            MeshState.BOOTSTRAPPED, "bootstrap_started"
        )

        start = time.monotonic()

        for phase in _BOOTSTRAP_ORDER:
            if time.monotonic() - start > timeout_s:
                self._failed_phase = phase
                logger.error(
                    "Bootstrap timeout at phase: %s", phase.value
                )
                await self._rollback()
                self._lifecycle.transition_to(
                    MeshState.FAILED, "bootstrap_timeout"
                )
                return self._build_result(False, phase)

            init_fn = self._phases.get(phase)
            if init_fn is None:
                self._phase_results[phase.value] = {
                    "success": True,
                    "skipped": True,
                }
                self._completed_phases.append(phase)
                continue

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
                logger.info(
                    "Bootstrap phase '%s' completed in %.3fs.",
                    phase.value,
                    duration,
                )
            except Exception as exc:
                self._failed_phase = phase
                logger.error(
                    "Bootstrap phase '%s' failed: %s",
                    phase.value,
                    exc,
                )
                await self._rollback()
                self._lifecycle.transition_to(
                    MeshState.FAILED, f"bootstrap_failed: {phase.value}"
                )
                return self._build_result(False, phase)

        self._lifecycle.transition_to(
            MeshState.RUNNING, "bootstrap_completed"
        )

        result = self._build_result(True)
        self._last_startup = result

        if self._publisher:
            await self._publisher.publish(MeshEvent.MESH_STARTED)

        logger.info(
            "Bootstrap completed: %d/%d phases in %.3fs.",
            len(self._completed_phases),
            len(_BOOTSTRAP_ORDER),
            time.monotonic() - start,
        )
        return result

    async def _rollback(self) -> None:
        """Rollback completed phases in reverse order."""
        self._rolled_back = True
        logger.warning(
            "Rolling bootstrap back due to failure."
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
        failed_phase: Optional[BootstrapPhase] = None,
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
                f"MeshBootstrap(completed={len(self._completed_phases)}/"
                f"{len(_BOOTSTRAP_ORDER)})"
            )
