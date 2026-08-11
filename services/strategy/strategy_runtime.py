"""
Production Strategy Runtime — execution sandbox for live strategies.

Manages the runtime environment for deployed strategies, including
concurrency control, resource allocation, health monitoring, and the
execution context for each running strategy.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SlotState(str, Enum):
    """State of a runtime execution slot."""
    ALLOCATED = "allocated"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class RuntimeSlot:
    """An execution slot for a single strategy instance."""

    slot_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    strategy_id: str = ""
    state: SlotState = SlotState.ALLOCATED

    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=dict)

    # Execution context
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    max_execution_time_ms: Optional[float] = None

    # Resources
    cpu_limit: float = 1.0
    memory_limit_mb: int = 512
    memory_used_mb: int = 0

    # Metrics
    execution_count: int = 0
    error_count: int = 0
    total_execution_time_ms: float = 0.0

    # Custom state
    variables: Dict[str, Any] = field(default_factory=dict)

    @property
    def uptime_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.stopped_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()

    @property
    def is_active(self) -> bool:
        return self.state in (SlotState.RUNNING, SlotState.PAUSED)

    def heartbeat(self) -> None:
        self.last_heartbeat = datetime.now(timezone.utc)

    def record_execution(self, duration_ms: float, success: bool = True) -> None:
        self.execution_count += 1
        self.total_execution_time_ms += duration_ms
        if not success:
            self.error_count += 1

    @property
    def avg_execution_time_ms(self) -> float:
        if self.execution_count == 0:
            return 0.0
        return self.total_execution_time_ms / self.execution_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "strategy_id": self.strategy_id,
            "state": self.state.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "execution_count": self.execution_count,
            "error_count": self.error_count,
            "avg_execution_time_ms": round(self.avg_execution_time_ms, 2),
            "memory_used_mb": self.memory_used_mb,
            "variables": self.variables,
        }


@dataclass
class RuntimeQuota:
    """Global resource quota for the strategy runtime."""
    max_concurrent_slots: int = 50
    total_cpu_limit: float = 32.0
    total_memory_mb: int = 16384


class StrategyRuntime:
    """Execution sandbox for production strategies.

    Manages individual runtime slots for each deployed strategy,
    enforces resource quotas, tracks heartbeat, and provides
    the execution context for strategy code.

    Usage:
        runtime = StrategyRuntime()
        await runtime.initialize()
        await runtime.prepare("strategy_1", package, config={})
        await runtime.start("strategy_1")
        slot = runtime.get_slot("strategy_1")
        await runtime.stop("strategy_1")
        await runtime.shutdown()
    """

    def __init__(self, quota: Optional[RuntimeQuota] = None) -> None:
        self._lock = threading.Lock()
        self._slots: Dict[str, RuntimeSlot] = {}
        self._quota = quota or RuntimeQuota()
        self._initialized: bool = False
        logger.info("StrategyRuntime created (quota: %d slots)", self._quota.max_concurrent_slots)

    # ── Lifecycle ──

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("StrategyRuntime initialized")

    async def shutdown(self) -> None:
        with self._lock:
            for slot in self._slots.values():
                if slot.is_active:
                    slot.state = SlotState.STOPPED
                    slot.stopped_at = datetime.now(timezone.utc)
                    logger.warning("Force-stopped slot: %s (%s)", slot.strategy_id, slot.slot_id)
            self._slots.clear()
        self._initialized = False
        logger.info("StrategyRuntime shut down")

    # ── Slot Management ──

    async def prepare(
        self,
        strategy_id: str,
        package: Any,
        config: Optional[Dict[str, Any]] = None,
    ) -> RuntimeSlot:
        """Allocate a runtime slot for a strategy.

        Validates resource availability and creates a new slot.
        """
        with self._lock:
            if strategy_id in self._slots:
                existing = self._slots[strategy_id]
                if existing.is_active:
                    raise RuntimeError(f"Slot already active for {strategy_id}: {existing.state.value}")
                del self._slots[strategy_id]

            if len(self._slots) >= self._quota.max_concurrent_slots:
                raise RuntimeError(
                    f"Maximum concurrent slots reached ({self._quota.max_concurrent_slots})"
                )

            slot = RuntimeSlot(
                strategy_id=strategy_id,
                state=SlotState.ALLOCATED,
                config=config or {},
                cpu_limit=package.manifest.resources.cpu_cores,
                memory_limit_mb=package.manifest.resources.memory_mb,
            )
            self._slots[strategy_id] = slot
            logger.info("Slot allocated: %s (%s), cpu=%.1f, mem=%dMB",
                        strategy_id, slot.slot_id, slot.cpu_limit, slot.memory_limit_mb)
            return slot

    async def start(self, strategy_id: str) -> RuntimeSlot:
        """Start execution for a strategy's runtime slot."""
        slot = self._get_slot(strategy_id)
        if slot.state == SlotState.RUNNING:
            logger.warning("Slot already running: %s", strategy_id)
            return slot

        slot.state = SlotState.INITIALIZING
        slot.started_at = datetime.now(timezone.utc)
        slot.heartbeat()

        # Simulate initialization
        await self._simulate_init(slot)

        slot.state = SlotState.RUNNING
        logger.info("Slot started: %s", strategy_id)
        return slot

    async def stop(self, strategy_id: str) -> RuntimeSlot:
        """Stop a running strategy's runtime slot."""
        slot = self._get_slot(strategy_id)
        slot.state = SlotState.STOPPING
        slot.stopped_at = datetime.now(timezone.utc)
        slot.state = SlotState.STOPPED
        logger.info("Slot stopped: %s (uptime=%.1fs)", strategy_id, slot.uptime_seconds)
        return slot

    async def pause(self, strategy_id: str) -> RuntimeSlot:
        """Pause a running strategy."""
        slot = self._get_slot(strategy_id)
        if slot.state != SlotState.RUNNING:
            raise RuntimeError(f"Cannot pause slot in state: {slot.state.value}")
        slot.state = SlotState.PAUSED
        logger.info("Slot paused: %s", strategy_id)
        return slot

    async def resume(self, strategy_id: str) -> RuntimeSlot:
        """Resume a paused strategy."""
        slot = self._get_slot(strategy_id)
        if slot.state != SlotState.PAUSED:
            raise RuntimeError(f"Cannot resume slot in state: {slot.state.value}")
        slot.state = SlotState.RUNNING
        slot.heartbeat()
        logger.info("Slot resumed: %s", strategy_id)
        return slot

    # ── Queries ──

    def get_slot(self, strategy_id: str) -> Optional[RuntimeSlot]:
        """Get the runtime slot for a strategy."""
        return self._slots.get(strategy_id)

    def get_status(self, strategy_id: str) -> Dict[str, Any]:
        """Get runtime status for a strategy."""
        slot = self._slots.get(strategy_id)
        if slot is None:
            return {"allocated": False}
        return slot.to_dict()

    def list_running(self) -> List[str]:
        """List all running strategy IDs."""
        with self._lock:
            return [sid for sid, s in self._slots.items() if s.is_active]

    @property
    def running_count(self) -> int:
        return len(self.list_running())

    @property
    def total_slots(self) -> int:
        return len(self._slots)

    def get_snapshot_data(self, strategy_id: str) -> Dict[str, Any]:
        """Export runtime state for snapshotting."""
        slot = self._slots.get(strategy_id)
        if slot is None:
            return {}
        return {
            "state": slot.state.value,
            "variables": dict(slot.variables),
            "execution_count": slot.execution_count,
            "error_count": slot.error_count,
            "started_at": slot.started_at.isoformat() if slot.started_at else None,
        }

    def restore_from_snapshot(self, strategy_id: str, data: Dict[str, Any]) -> None:
        """Restore runtime state from a snapshot."""
        slot = self._slots.get(strategy_id)
        if slot is None:
            return
        slot.variables = data.get("variables", {})
        logger.info("Runtime state restored from snapshot: %s", strategy_id)

    # ── Internals ──

    def _get_slot(self, strategy_id: str) -> RuntimeSlot:
        """Get slot or raise."""
        slot = self._slots.get(strategy_id)
        if slot is None:
            raise KeyError(f"No runtime slot for: {strategy_id}")
        return slot

    async def _simulate_init(self, slot: RuntimeSlot) -> None:
        """Simulate strategy initialization delay."""
        time.sleep(0.01)  # minimal delay for real-world simulation

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_slots": len(self._slots),
                "running_count": self.running_count,
                "quota_max": self._quota.max_concurrent_slots,
                "initialized": self._initialized,
            }
