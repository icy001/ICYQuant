"""
Signal Runtime — Execution sandbox for signal processing.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Provides:
    - Concurrent signal generation slots
    - Resource quota management
    - Heartbeat monitoring for long-running signal computations
    - Graceful shutdown of in-flight signal tasks
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SlotStatus(str, Enum):
    """Signal runtime slot lifecycle."""
    IDLE = "IDLE"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    RANKING = "RANKING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class RuntimeSlot:
    """A single signal generation execution slot."""
    slot_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    strategy_id: str = ""
    status: SlotStatus = SlotStatus.IDLE
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    heartbeat_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeQuota:
    """Resource limits for signal runtime."""
    max_concurrent_slots: int = 32
    max_slot_duration_seconds: float = 300.0
    heartbeat_interval_seconds: float = 10.0
    heartbeat_timeout_seconds: float = 30.0


# ---------------------------------------------------------------------------
# Signal Runtime
# ---------------------------------------------------------------------------

class SignalRuntime:
    """Execution sandbox for signal processing tasks.

    Manages concurrency, resource quotas, and lifecycle of signal generation slots.
    """

    def __init__(self, quota: Optional[RuntimeQuota] = None):
        self.quota = quota or RuntimeQuota()
        self._slots: Dict[str, RuntimeSlot] = {}
        self._semaphore = asyncio.Semaphore(self.quota.max_concurrent_slots)
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._initialized = False
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("SignalRuntime initialized (max_slots=%d)", self.quota.max_concurrent_slots)

    async def shutdown(self) -> None:
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        # Cancel all active slots
        for slot in list(self._slots.values()):
            if slot.status in (SlotStatus.GENERATING, SlotStatus.VALIDATING, SlotStatus.RANKING):
                slot.status = SlotStatus.CANCELLED
        self._initialized = False
        logger.info("SignalRuntime shut down")

    # ------------------------------------------------------------------
    # Slot Management
    # ------------------------------------------------------------------

    async def acquire_slot(self, strategy_id: str) -> RuntimeSlot:
        """Acquire a slot for signal generation. Blocks if at capacity."""
        await self._semaphore.acquire()
        slot = RuntimeSlot(strategy_id=strategy_id)
        self._slots[slot.slot_id] = slot
        logger.debug("Slot %s acquired for strategy %s", slot.slot_id, strategy_id)
        return slot

    async def start_slot(self, slot_id: str) -> None:
        """Mark a slot as actively generating."""
        slot = self._slots.get(slot_id)
        if not slot:
            raise KeyError(f"Slot {slot_id} not found")
        slot.status = SlotStatus.GENERATING
        slot.started_at = datetime.now(timezone.utc)
        slot.heartbeat_at = datetime.now(timezone.utc)

    async def update_slot_status(self, slot_id: str, status: SlotStatus) -> None:
        """Update the processing status of a slot."""
        slot = self._slots.get(slot_id)
        if not slot:
            raise KeyError(f"Slot {slot_id} not found")
        slot.status = status

    async def heartbeat(self, slot_id: str) -> None:
        """Record a heartbeat for a running slot."""
        slot = self._slots.get(slot_id)
        if slot:
            slot.heartbeat_at = datetime.now(timezone.utc)

    async def release_slot(self, slot_id: str, error: Optional[str] = None) -> None:
        """Release a slot back to the pool."""
        slot = self._slots.get(slot_id)
        if slot:
            slot.finished_at = datetime.now(timezone.utc)
            slot.error = error
            if error:
                slot.status = SlotStatus.FAILED
            elif slot.status not in (SlotStatus.COMPLETED, SlotStatus.CANCELLED):
                slot.status = SlotStatus.COMPLETED
            self._semaphore.release()
            logger.debug("Slot %s released (status=%s)", slot_id, slot.status.value)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def active_slot_count(self) -> int:
        """Count of currently active (non-idle, non-terminal) slots."""
        active = {SlotStatus.GENERATING, SlotStatus.VALIDATING, SlotStatus.RANKING}
        return sum(1 for s in self._slots.values() if s.status in active)

    def available_slots(self) -> int:
        """Number of slots currently available."""
        return self.quota.max_concurrent_slots - self.active_slot_count()

    def slot_status(self, slot_id: str) -> Optional[SlotStatus]:
        slot = self._slots.get(slot_id)
        return slot.status if slot else None

    # ------------------------------------------------------------------
    # Heartbeat Monitor
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        """Monitor running slots and cancel those that have timed out."""
        while self._running:
            try:
                await asyncio.sleep(self.quota.heartbeat_interval_seconds)
                now = datetime.now(timezone.utc)
                for slot in list(self._slots.values()):
                    if slot.status not in (SlotStatus.GENERATING, SlotStatus.VALIDATING, SlotStatus.RANKING):
                        continue
                    # Check duration limit
                    if slot.started_at:
                        elapsed = (now - slot.started_at).total_seconds()
                        if elapsed > self.quota.max_slot_duration_seconds:
                            logger.warning(
                                "Slot %s exceeded max duration (%.1fs), cancelling",
                                slot.slot_id, elapsed,
                            )
                            slot.status = SlotStatus.CANCELLED
                            slot.error = "Max duration exceeded"
                            self._semaphore.release()
                            continue
                    # Check heartbeat timeout
                    if slot.heartbeat_at:
                        since_heartbeat = (now - slot.heartbeat_at).total_seconds()
                        if since_heartbeat > self.quota.heartbeat_timeout_seconds:
                            logger.warning(
                                "Slot %s heartbeat timeout (%.1fs), cancelling",
                                slot.slot_id, since_heartbeat,
                            )
                            slot.status = SlotStatus.CANCELLED
                            slot.error = "Heartbeat timeout"
                            self._semaphore.release()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Heartbeat loop error")
