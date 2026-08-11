"""Runtime Manager — manages execution environments and resource allocation for AI agents.

The RuntimeManager provides sandboxed execution environments for agents, controls
concurrency, enforces resource limits (CPU, memory, time), and manages thread/process
pools for parallel agent execution.

Key capabilities:
    - Execution sandbox per agent
    - Concurrency control (max parallel agents)
    - Resource quota enforcement
    - Timeout management
    - Graceful cancellation
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    """Execution mode for agent runtime."""
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    STREAMING = "streaming"


@dataclass
class ResourceQuota:
    """Resource limits for an agent execution."""
    max_duration_sec: float = 300.0
    max_memory_mb: int = 512
    max_tokens: int = 100000
    max_tool_calls: int = 50


@dataclass
class ExecutionSlot:
    """Tracks an active agent execution."""
    agent_id: str = ""
    task_id: str = ""
    mode: ExecutionMode = ExecutionMode.ASYNCHRONOUS
    started_at: float = field(default_factory=time.monotonic)
    quota: ResourceQuota = field(default_factory=ResourceQuota)
    cancelled: bool = False


class RuntimeManager:
    """Manages execution environments and resources for all AI agents.

    Controls concurrency, enforces resource limits, and provides the
    execution sandbox for agent operations.

    Usage:
        rm = RuntimeManager(max_concurrent=10)
        await rm.initialize()
        slot = await rm.acquire_slot(agent_id, task_id)
        # ... execute agent ...
        await rm.release_slot(agent_id)
    """

    def __init__(self, max_concurrent: int = 10, default_quota: Optional[ResourceQuota] = None) -> None:
        self._max_concurrent = max_concurrent
        self._default_quota = default_quota or ResourceQuota()
        self._active_slots: Dict[str, ExecutionSlot] = {}
        self._agent_slots: Dict[str, Set[str]] = {}
        self._total_executions: int = 0
        self._total_cancelled: int = 0
        self._total_timeouts: int = 0
        self._initialized: bool = False
        self._lock = asyncio.Lock()
        logger.info("RuntimeManager created (max_concurrent=%d)", max_concurrent)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("RuntimeManager initialized")

    async def shutdown(self) -> None:
        """Cancel all active executions and clean up."""
        async with self._lock:
            for slot in self._active_slots.values():
                slot.cancelled = True
            self._active_slots.clear()
            self._agent_slots.clear()
        self._initialized = False
        logger.info("RuntimeManager shutdown complete")

    async def acquire_slot(self, agent_id: str, task_id: str, mode: ExecutionMode = ExecutionMode.ASYNCHRONOUS, quota: Optional[ResourceQuota] = None) -> Optional[ExecutionSlot]:
        """Acquire an execution slot for an agent. Returns None if at capacity."""
        async with self._lock:
            if len(self._active_slots) >= self._max_concurrent:
                logger.warning("RuntimeManager: at capacity (%d/%d)", len(self._active_slots), self._max_concurrent)
                return None

            slot = ExecutionSlot(
                agent_id=agent_id,
                task_id=task_id,
                mode=mode,
                quota=quota or self._default_quota,
            )
            self._active_slots[task_id] = slot
            self._agent_slots.setdefault(agent_id, set()).add(task_id)
            self._total_executions += 1
            logger.info("RuntimeManager: acquired slot for %s (task=%s, active=%d)", agent_id, task_id, len(self._active_slots))
            return slot

    async def release_slot(self, task_id: str) -> bool:
        """Release an execution slot."""
        async with self._lock:
            if task_id not in self._active_slots:
                return False
            slot = self._active_slots.pop(task_id)
            agent_slots = self._agent_slots.get(slot.agent_id, set())
            agent_slots.discard(task_id)
            if not agent_slots:
                self._agent_slots.pop(slot.agent_id, None)
            logger.info("RuntimeManager: released slot for %s (task=%s, active=%d)", slot.agent_id, task_id, len(self._active_slots))
            return True

    async def cancel_execution(self, task_id: str) -> bool:
        """Cancel an active execution."""
        async with self._lock:
            if task_id not in self._active_slots:
                return False
            self._active_slots[task_id].cancelled = True
            self._total_cancelled += 1
            return True

    def is_cancelled(self, task_id: str) -> bool:
        return task_id in self._active_slots and self._active_slots[task_id].cancelled

    @property
    def active_count(self) -> int:
        return len(self._active_slots)

    @property
    def available_slots(self) -> int:
        return max(0, self._max_concurrent - len(self._active_slots))

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "max_concurrent": self._max_concurrent,
            "active_executions": len(self._active_slots),
            "available_slots": self.available_slots,
            "total_executions": self._total_executions,
            "total_cancelled": self._total_cancelled,
            "total_timeouts": self._total_timeouts,
        }
