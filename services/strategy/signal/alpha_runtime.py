"""
Alpha Runtime — Execution sandbox for alpha computation.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Provides:
    - Concurrent alpha computation slots
    - Resource quota management
    - Timeout enforcement for alpha models
    - Heartbeat monitoring
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AlphaSlotStatus(str, Enum):
    IDLE = "IDLE"
    COMPUTING = "COMPUTING"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class AlphaSlot:
    """A single alpha computation slot."""
    slot_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    alpha_id: str = ""
    instrument: str = ""
    status: AlphaSlotStatus = AlphaSlotStatus.IDLE
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class AlphaQuota:
    """Resource limits for alpha runtime."""
    max_concurrent_slots: int = 64
    max_compute_duration_seconds: float = 120.0
    heartbeat_interval_seconds: float = 5.0


# ---------------------------------------------------------------------------
# Alpha Runtime
# ---------------------------------------------------------------------------

class AlphaRuntime:
    """Execution sandbox for alpha computations."""

    def __init__(self, quota: Optional[AlphaQuota] = None):
        self.quota = quota or AlphaQuota()
        self._slots: Dict[str, AlphaSlot] = {}
        self._semaphore = asyncio.Semaphore(self.quota.max_concurrent_slots)
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
        logger.info("AlphaRuntime initialized (max_slots=%d)", self.quota.max_concurrent_slots)

    async def shutdown(self) -> None:
        self._running = False
        for slot in list(self._slots.values()):
            if slot.status == AlphaSlotStatus.COMPUTING:
                slot.status = AlphaSlotStatus.TIMEOUT
        self._initialized = False
        logger.info("AlphaRuntime shut down")

    # ------------------------------------------------------------------
    # Slot Management
    # ------------------------------------------------------------------

    async def acquire_slot(self, alpha_id: str, instrument: str) -> AlphaSlot:
        """Acquire a computation slot."""
        await self._semaphore.acquire()
        slot = AlphaSlot(alpha_id=alpha_id, instrument=instrument)
        self._slots[slot.slot_id] = slot
        return slot

    async def start_compute(self, slot_id: str) -> None:
        slot = self._slots.get(slot_id)
        if not slot:
            raise KeyError(f"Slot {slot_id} not found")
        slot.status = AlphaSlotStatus.COMPUTING
        slot.started_at = datetime.now(timezone.utc)

    async def complete_slot(self, slot_id: str, error: Optional[str] = None) -> None:
        slot = self._slots.get(slot_id)
        if slot:
            slot.finished_at = datetime.now(timezone.utc)
            slot.error = error
            slot.status = AlphaSlotStatus.FAILED if error else AlphaSlotStatus.COMPLETED
            self._semaphore.release()

    async def run_with_timeout(self, alpha_id: str, instrument: str,
                               coro) -> Any:
        """Run an alpha computation with timeout enforcement."""
        slot = await self.acquire_slot(alpha_id, instrument)
        await self.start_compute(slot.slot_id)

        try:
            result = await asyncio.wait_for(
                coro,
                timeout=self.quota.max_compute_duration_seconds,
            )
            await self.complete_slot(slot.slot_id)
            return result
        except asyncio.TimeoutError:
            await self.complete_slot(slot.slot_id, error="Computation timeout")
            slot.status = AlphaSlotStatus.TIMEOUT
            raise
        except Exception as e:
            await self.complete_slot(slot.slot_id, error=str(e))
            raise

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def active_count(self) -> int:
        return sum(1 for s in self._slots.values() if s.status == AlphaSlotStatus.COMPUTING)

    def available_slots(self) -> int:
        return self.quota.max_concurrent_slots - self.active_count()
