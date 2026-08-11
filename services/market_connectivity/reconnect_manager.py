"""
Reconnect Manager — Handles automatic reconnection with exponential
backoff, retry strategies, and resumption support.

Disconnect → Retry → Backoff → Reconnect → Resume
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ReconnectState(str, Enum):
    IDLE = "idle"
    RETRYING = "retrying"
    BACKING_OFF = "backing_off"
    RECONNECTING = "reconnecting"
    RECONNECTED = "reconnected"
    FAILED = "failed"
    SUSPENDED = "suspended"


class ReconnectPolicy(str, Enum):
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"


@dataclass
class ReconnectRecord:
    connection_id: str
    exchange_id: str
    state: ReconnectState = ReconnectState.IDLE
    retry_count: int = 0
    max_retries: int = 10
    base_delay: float = 1.0
    max_delay: float = 60.0
    current_delay: float = 1.0
    policy: ReconnectPolicy = ReconnectPolicy.EXPONENTIAL_BACKOFF
    last_attempt: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_error: str = ""
    total_retries: int = 0
    total_reconnects: int = 0


class ReconnectManager:
    """
    Manages automatic reconnection with configurable backoff strategies.

    Supports exponential backoff, linear backoff, fixed delay, and
    immediate reconnect policies with jitter and max retry limits.

    Usage::

        manager = ReconnectManager()
        await manager.initialize()
        await manager.register("conn_001", "binance", policy=ReconnectPolicy.EXPONENTIAL_BACKOFF)
        success = await manager.reconnect("conn_001")
    """

    def __init__(self) -> None:
        self._records: dict[str, ReconnectRecord] = {}
        self._connect_callback: Optional[Callable] = None
        self._disconnect_callback: Optional[Callable] = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the reconnect manager."""
        logger.info("ReconnectManager initialized.")

    def set_connect_callback(self, callback: Callable) -> None:
        """Set the callback for performing actual connection."""
        self._connect_callback = callback

    def set_disconnect_callback(self, callback: Callable) -> None:
        """Set the callback for performing actual disconnection."""
        self._disconnect_callback = callback

    # ---- Registration ----

    async def register(
        self,
        connection_id: str,
        exchange_id: str,
        policy: ReconnectPolicy = ReconnectPolicy.EXPONENTIAL_BACKOFF,
        max_retries: int = 10,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ) -> None:
        """Register a connection for automatic reconnection."""
        async with self._lock:
            self._records[connection_id] = ReconnectRecord(
                connection_id=connection_id,
                exchange_id=exchange_id,
                policy=policy,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                current_delay=base_delay,
            )
        logger.debug("Registered reconnect manager for: %s", connection_id)

    async def unregister(self, connection_id: str) -> bool:
        """Remove a connection from reconnection management."""
        async with self._lock:
            return self._records.pop(connection_id, None) is not None

    # ---- Reconnect Operations ----

    async def reconnect(self, connection_id: str) -> bool:
        """Attempt to reconnect with backoff strategy."""
        record = self._records.get(connection_id)
        if record is None:
            logger.error("Connection not registered for reconnect: %s", connection_id)
            return False

        if record.retry_count >= record.max_retries:
            record.state = ReconnectState.FAILED
            logger.error("Max retries reached for %s", connection_id)
            return False

        record.state = ReconnectState.RETRYING
        record.last_attempt = datetime.now(timezone.utc)

        # Calculate backoff delay
        delay = self._calculate_delay(record)
        record.current_delay = delay

        # Apply jitter
        jitter = delay * 0.1 * random.random()
        total_delay = delay + jitter

        logger.info(
            "Reconnecting %s: attempt %d/%d, delay=%.2fs (policy=%s)",
            connection_id, record.retry_count + 1, record.max_retries,
            total_delay, record.policy.value,
        )

        # Disconnect first if needed
        record.state = ReconnectState.BACKING_OFF
        if self._disconnect_callback:
            try:
                await self._disconnect_callback(connection_id)
            except Exception:
                logger.exception("Disconnect failed during reconnect: %s", connection_id)

        await asyncio.sleep(total_delay)

        # Attempt reconnection
        record.state = ReconnectState.RECONNECTING
        try:
            if self._connect_callback:
                await self._connect_callback(connection_id)
            else:
                await asyncio.sleep(0.01)  # placeholder

            record.state = ReconnectState.RECONNECTED
            record.retry_count = 0
            record.current_delay = record.base_delay
            record.last_success = datetime.now(timezone.utc)
            record.total_reconnects += 1
            logger.info("Reconnected successfully: %s", connection_id)
            return True

        except Exception as e:
            record.retry_count += 1
            record.total_retries += 1
            record.last_error = str(e)
            logger.warning(
                "Reconnect failed for %s (attempt %d): %s",
                connection_id, record.retry_count, str(e),
            )
            return False

    async def reset(self, connection_id: str) -> None:
        """Reset the reconnect state for a connection."""
        record = self._records.get(connection_id)
        if record:
            record.state = ReconnectState.IDLE
            record.retry_count = 0
            record.current_delay = record.base_delay
            record.last_error = ""

    async def get_state(self, connection_id: str) -> Optional[ReconnectState]:
        """Get the current reconnect state."""
        record = self._records.get(connection_id)
        return record.state if record else None

    async def get_record(self, connection_id: str) -> Optional[ReconnectRecord]:
        """Get the full reconnect record."""
        return self._records.get(connection_id)

    async def get_summary(self) -> dict[str, Any]:
        """Get reconnect summary for all connections."""
        total = len(self._records)
        reconnecting = sum(1 for r in self._records.values() if r.state == ReconnectState.RECONNECTING)
        failed = sum(1 for r in self._records.values() if r.state == ReconnectState.FAILED)
        total_reconnects = sum(r.total_reconnects for r in self._records.values())

        return {
            "total": total,
            "reconnecting": reconnecting,
            "failed": failed,
            "total_reconnects": total_reconnects,
        }

    def _calculate_delay(self, record: ReconnectRecord) -> float:
        """Calculate the backoff delay based on the policy."""
        if record.policy == ReconnectPolicy.IMMEDIATE:
            return 0.0
        elif record.policy == ReconnectPolicy.FIXED_DELAY:
            return record.base_delay
        elif record.policy == ReconnectPolicy.LINEAR_BACKOFF:
            delay = record.base_delay * (record.retry_count + 1)
            return min(delay, record.max_delay)
        elif record.policy == ReconnectPolicy.EXPONENTIAL_BACKOFF:
            delay = record.base_delay * (2 ** record.retry_count)
            return min(delay, record.max_delay)
        return record.base_delay
