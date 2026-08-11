"""
Decision Runtime
================
Execution sandbox for portfolio decision computations with
concurrency control, timeout enforcement, and heartbeat monitoring.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

logger = logging.getLogger(__name__)


class SlotStatus(str, Enum):
    """Status of a runtime slot."""

    IDLE = "idle"
    ACTIVE = "active"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class DecisionSlot:
    """An execution slot tracking a single decision computation."""

    slot_id: str = field(default_factory=lambda: f"ds_{uuid4().hex[:8]}")
    task_name: str = ""
    status: SlotStatus = SlotStatus.IDLE
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        self.status = SlotStatus.ACTIVE
        self.started_at = datetime.now(timezone.utc)

    def complete(self, duration_ms: float) -> None:
        self.status = SlotStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.duration_ms = duration_ms

    def fail(self, error: str) -> None:
        self.status = SlotStatus.ERROR
        self.completed_at = datetime.now(timezone.utc)
        self.error = error


@dataclass
class DecisionQuota:
    """Resource quota for the decision runtime."""

    max_concurrent: int = 10
    max_per_strategy: int = 3
    max_per_portfolio: int = 5
    timeout_seconds: float = 30.0
    heartbeat_interval_seconds: float = 5.0
    max_retries: int = 3


class DecisionRuntime:
    """
    Execution sandbox for portfolio decision computations.

    Features:
    - Concurrency control via slots
    - Timeout enforcement
    - Heartbeat monitoring
    - Per-strategy and per-portfolio quotas
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self._quota = DecisionQuota(
            max_concurrent=config.get("max_concurrent", 10),
            max_per_strategy=config.get("max_per_strategy", 3),
            max_per_portfolio=config.get("max_per_portfolio", 5),
            timeout_seconds=config.get("timeout_seconds", 30.0),
            heartbeat_interval_seconds=config.get("heartbeat_interval_seconds", 5.0),
            max_retries=config.get("max_retries", 3),
        )
        self._initialized = False

        # Active slots
        self._active_slots: Dict[str, DecisionSlot] = {}
        self._slot_history: List[DecisionSlot] = []
        self._semaphore = asyncio.Semaphore(self._quota.max_concurrent)

        # Per-strategy / per-portfolio counters
        self._strategy_active: Dict[str, int] = {}
        self._portfolio_active: Dict[str, int] = {}

        # Tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._initialized = True
        logger.info("DecisionRuntime initialized (max_concurrent=%d)", self._quota.max_concurrent)

    async def shutdown(self) -> None:
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        # Cancel all active slots
        for slot in list(self._active_slots.values()):
            slot.status = SlotStatus.CANCELLED
        self._active_slots.clear()
        self._initialized = False
        logger.info("DecisionRuntime shut down")

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run(
        self,
        task_name: str,
        coro: Callable[..., Any],
        strategy_id: str = "",
        portfolio_id: str = "",
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute a decision computation with concurrency control and timeout.

        Args:
            task_name: Human-readable task name.
            coro: Async callable to execute.
            strategy_id: Associated strategy for quota tracking.
            portfolio_id: Associated portfolio for quota tracking.

        Returns:
            Result of the coroutine.

        Raises:
            asyncio.TimeoutError: If execution exceeds timeout.
            RuntimeError: If quota limits are exceeded.
        """
        if not self._initialized:
            await self.initialize()

        # Check per-strategy quota
        if strategy_id:
            current = self._strategy_active.get(strategy_id, 0)
            if current >= self._quota.max_per_strategy:
                raise RuntimeError(
                    f"Per-strategy quota exceeded for {strategy_id}: "
                    f"{current}/{self._quota.max_per_strategy}"
                )

        # Check per-portfolio quota
        if portfolio_id:
            current = self._portfolio_active.get(portfolio_id, 0)
            if current >= self._quota.max_per_portfolio:
                raise RuntimeError(
                    f"Per-portfolio quota exceeded for {portfolio_id}: "
                    f"{current}/{self._quota.max_per_portfolio}"
                )

        slot = DecisionSlot(task_name=task_name)
        self._active_slots[slot.slot_id] = slot

        # Increment counters
        if strategy_id:
            self._strategy_active[strategy_id] = self._strategy_active.get(strategy_id, 0) + 1
        if portfolio_id:
            self._portfolio_active[portfolio_id] = self._portfolio_active.get(portfolio_id, 0) + 1

        try:
            async with self._semaphore:
                slot.start()
                start_time = time.monotonic()

                try:
                    result = await asyncio.wait_for(
                        coro(*args, **kwargs),
                        timeout=self._quota.timeout_seconds,
                    )
                    elapsed = (time.monotonic() - start_time) * 1000
                    slot.complete(elapsed)
                    logger.debug("Slot %s completed in %.2fms", slot.slot_id, elapsed)
                    return result

                except asyncio.TimeoutError:
                    slot.fail("timeout")
                    logger.error("Slot %s timed out after %.0fs", slot.slot_id, self._quota.timeout_seconds)
                    raise

                except Exception as exc:
                    slot.fail(str(exc))
                    logger.error("Slot %s failed: %s", slot.slot_id, exc)
                    raise

        finally:
            self._active_slots.pop(slot.slot_id, None)
            self._slot_history.append(slot)
            if strategy_id:
                self._strategy_active[strategy_id] = max(0, self._strategy_active.get(strategy_id, 1) - 1)
            if portfolio_id:
                self._portfolio_active[portfolio_id] = max(0, self._portfolio_active.get(portfolio_id, 1) - 1)

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        """Background task to monitor active slots for stalled computations."""
        while self._running:
            try:
                await asyncio.sleep(self._quota.heartbeat_interval_seconds)
                now = datetime.now(timezone.utc)
                for slot_id, slot in list(self._active_slots.items()):
                    if slot.started_at:
                        elapsed = (now - slot.started_at).total_seconds()
                        if elapsed > self._quota.timeout_seconds * 1.5:
                            logger.warning(
                                "Slot %s (%s) stalled for %.1fs - forcing timeout",
                                slot_id,
                                slot.task_name,
                                elapsed,
                            )
                            slot.status = SlotStatus.TIMEOUT
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Heartbeat loop error")

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def active_count(self) -> int:
        return len(self._active_slots)

    @property
    def total_processed(self) -> int:
        return len(self._slot_history)

    def get_active_slots(self) -> List[DecisionSlot]:
        return list(self._active_slots.values())

    def get_quota_usage(self) -> Dict[str, Any]:
        return {
            "active_slots": len(self._active_slots),
            "max_concurrent": self._quota.max_concurrent,
            "per_strategy": dict(self._strategy_active),
            "per_portfolio": dict(self._portfolio_active),
        }

    @property
    def is_initialized(self) -> bool:
        return self._initialized
