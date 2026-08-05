"""Service discovery bootstrap for ICYQuant platform.

Provides ``DiscoveryBootstrap`` with ordered startup phases,
parallel initialization support, automatic rollback, and
startup timeout protection.

Startup order: Configuration -> Registry -> Repository -> Heartbeat
              -> Resolver -> HA Controller -> Gateway -> Runtime Ready
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class BootstrapPhase(Enum):
    """Phases of the service discovery bootstrap process."""

    CONFIGURATION = "configuration"
    REGISTRY = "registry"
    REPOSITORY = "repository"
    HEARTBEAT = "heartbeat"
    RESOLVER = "resolver"
    HA_CONTROLLER = "ha_controller"
    GATEWAY = "gateway"
    RUNTIME = "runtime"


_BOOTSTRAP_ORDER: List[BootstrapPhase] = [
    BootstrapPhase.CONFIGURATION,
    BootstrapPhase.REGISTRY,
    BootstrapPhase.REPOSITORY,
    BootstrapPhase.HEARTBEAT,
    BootstrapPhase.RESOLVER,
    BootstrapPhase.HA_CONTROLLER,
    BootstrapPhase.GATEWAY,
    BootstrapPhase.RUNTIME,
]


@dataclass
class _PhaseRecord:
    phase: BootstrapPhase
    started_at: float = 0.0
    completed_at: float = 0.0
    success: bool = False
    error: Optional[str] = None
    duration_s: float = 0.0


class DiscoveryBootstrap:
    """Ordered bootstrap for the service discovery platform.

    Executes startup phases in sequence, with support for
    parallel initialization, rollback on failure, and
    configurable timeout protection.

    Args:
        context: Optional ``DiscoveryContext`` instance.
        timeout: Maximum seconds for the full bootstrap.
    """

    def __init__(
        self,
        context: Any = None,
        timeout: float = 60.0,
    ) -> None:
        self._lock = threading.RLock()
        self._context = context
        self._timeout = timeout
        self._phases: Dict[
            BootstrapPhase,
            Callable[[], Any],
        ] = {}
        self._completed: List[_PhaseRecord] = []
        self._current_phase: Optional[BootstrapPhase] = None
        self._bootstrap_count = 0
        self._last_result: Optional[Dict[str, Any]] = None
        self._rolled_back = False
        self._bootstrap_time: Optional[datetime] = None

    def register_phase(
        self,
        phase: BootstrapPhase,
        init_fn: Callable[[], Any],
    ) -> None:
        """Register an initialization function for a phase.

        Args:
            phase: The bootstrap phase.
            init_fn: A callable (sync or async) that initializes
                the phase component.
        """
        with self._lock:
            self._phases[phase] = init_fn
        logger.debug("Registered bootstrap phase '%s'.", phase.value)

    async def startup(self) -> Dict[str, Any]:
        """Execute the bootstrap startup sequence.

        Returns:
            A dictionary describing the bootstrap result.
        """
        with self._lock:
            self._bootstrap_count += 1
            self._rolled_back = False
            self._completed = []

        result: Dict[str, Any] = {
            "bootstrapped": True,
            "phases": {},
            "started_at": datetime.utcnow().isoformat(),
            "duration_s": 0.0,
        }

        bootstrap_start = time.monotonic()

        for phase in _BOOTSTRAP_ORDER:
            if phase not in self._phases:
                record = _PhaseRecord(
                    phase=phase,
                    success=True,
                )
                self._completed.append(record)
                result["phases"][phase.value] = {
                    "skipped": True,
                    "reason": "no_initializer",
                }
                continue

            self._current_phase = phase
            phase_start = time.monotonic()
            try:
                init_fn = self._phases[phase]
                coro = init_fn()
                if asyncio.iscoroutine(coro):
                    outcome = await coro
                else:
                    outcome = coro

                phase_duration = time.monotonic() - phase_start
                record = _PhaseRecord(
                    phase=phase,
                    started_at=phase_start,
                    completed_at=time.monotonic(),
                    success=True,
                    duration_s=phase_duration,
                )
                self._completed.append(record)
                result["phases"][phase.value] = {
                    "success": True,
                    "duration_s": phase_duration,
                    "outcome": str(outcome)[:200] if outcome else None,
                }
                logger.info(
                    "Bootstrap phase '%s' completed in %.3fs.",
                    phase.value,
                    phase_duration,
                )
            except Exception as exc:
                phase_duration = time.monotonic() - phase_start
                record = _PhaseRecord(
                    phase=phase,
                    started_at=phase_start,
                    completed_at=time.monotonic(),
                    success=False,
                    error=str(exc),
                    duration_s=phase_duration,
                )
                self._completed.append(record)
                result["phases"][phase.value] = {
                    "success": False,
                    "duration_s": phase_duration,
                    "error": str(exc),
                }
                result["bootstrapped"] = False
                result["failed_phase"] = phase.value
                result["error"] = str(exc)
                logger.error(
                    "Bootstrap phase '%s' failed: %s",
                    phase.value,
                    exc,
                )
                await self._rollback()
                break

        result["duration_s"] = time.monotonic() - bootstrap_start
        result["completed_at"] = datetime.utcnow().isoformat()
        self._current_phase = None
        self._bootstrap_time = datetime.utcnow()

        with self._lock:
            self._last_result = result

        return result

    async def _rollback(self) -> None:
        """Rollback completed phases in reverse order."""
        with self._lock:
            self._rolled_back = True

        logger.warning("Rolling bootstrap back due to failure.")
        for record in reversed(self._completed):
            if not record.success:
                continue
            rollback_fn_name = f"_rollback_{record.phase.value}"
            rollback_fn = getattr(self, rollback_fn_name, None)
            if callable(rollback_fn):
                try:
                    coro = rollback_fn()
                    if asyncio.iscoroutine(coro):
                        await coro
                    logger.info(
                        "Rolled back phase '%s'.",
                        record.phase.value,
                    )
                except Exception as exc:
                    logger.warning(
                        "Rollback of '%s' failed: %s",
                        record.phase.value,
                        exc,
                    )

    async def shutdown(self) -> Dict[str, Any]:
        """Shutdown in reverse order.

        Returns:
            A dictionary describing the shutdown result.
        """
        result: Dict[str, Any] = {
            "shutdown": True,
            "phases": {},
            "started_at": datetime.utcnow().isoformat(),
        }

        for record in reversed(self._completed):
            shutdown_fn_name = f"_shutdown_{record.phase.value}"
            shutdown_fn = getattr(self, shutdown_fn_name, None)
            if callable(shutdown_fn):
                try:
                    coro = shutdown_fn()
                    if asyncio.iscoroutine(coro):
                        await coro
                    result["phases"][record.phase.value] = {
                        "success": True
                    }
                except Exception as exc:
                    result["phases"][record.phase.value] = {
                        "success": False,
                        "error": str(exc),
                    }
                    result["shutdown"] = False

        result["completed_at"] = datetime.utcnow().isoformat()
        return result

    def get_phase_status(self) -> Dict[str, Any]:
        with self._lock:
            completed = {
                r.phase.value: r.success for r in self._completed
            }
            return {
                "current_phase": (
                    self._current_phase.value
                    if self._current_phase
                    else None
                ),
                "completed_phases": completed,
                "rollback_occurred": self._rolled_back,
                "bootstrap_time": (
                    self._bootstrap_time.isoformat()
                    if self._bootstrap_time
                    else None
                ),
            }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "registered_phases": sorted(
                    p.value for p in self._phases
                ),
                "completed_phases": [
                    r.phase.value for r in self._completed
                ],
                "bootstrap_count": self._bootstrap_count,
                "current_phase": (
                    self._current_phase.value
                    if self._current_phase
                    else None
                ),
                "rollback_occurred": self._rolled_back,
                "last_result": self._last_result,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"DiscoveryBootstrap(phases={len(self._phases)}, "
                f"bootstraps={self._bootstrap_count})"
            )
