"""
Session Scheduler — Manages session scheduling policies across exchanges
including load balancing, priority ordering, and rate limit awareness.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .exchange_session import ExchangeSession, SessionType

logger = logging.getLogger(__name__)


class SchedulePolicy(str, Enum):
    """Session scheduling policies."""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    PRIORITY = "priority"
    RATE_LIMIT_AWARE = "rate_limit_aware"
    LATENCY_OPTIMIZED = "latency_optimized"


@dataclass
class ScheduleEntry:
    """A scheduled session entry."""
    session: ExchangeSession
    priority: int = 100
    weight: int = 1
    current_load: int = 0
    rate_limit_remaining: float = 1.0


class SessionScheduler:
    """
    Scheduler for distributing load across exchange sessions.

    Supports multiple scheduling policies: round-robin, least-loaded,
    priority-based, rate-limit-aware, and latency-optimized.

    Usage::

        scheduler = SessionScheduler(policy=SchedulePolicy.LEAST_LOADED)
        await scheduler.initialize()
        await scheduler.register_session(session, priority=100)
        best = await scheduler.select("binance", SessionType.MARKET_DATA)
    """

    def __init__(self, policy: SchedulePolicy = SchedulePolicy.ROUND_ROBIN) -> None:
        self.policy = policy
        self._entries: dict[str, list[ScheduleEntry]] = {}
        self._round_robin_index: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the session scheduler."""
        logger.info("SessionScheduler initialized with policy=%s", self.policy.value)

    # ---- Registration ----

    async def register_session(
        self,
        session: ExchangeSession,
        priority: int = 100,
        weight: int = 1,
    ) -> None:
        """Register a session for scheduling."""
        pool_key = f"{session.exchange_id}_{session.session_type.value}"
        async with self._lock:
            if pool_key not in self._entries:
                self._entries[pool_key] = []
                self._round_robin_index[pool_key] = 0

            # Avoid duplicates
            existing_ids = {e.session.session_id for e in self._entries[pool_key]}
            if session.session_id not in existing_ids:
                entry = ScheduleEntry(
                    session=session,
                    priority=priority,
                    weight=weight,
                )
                self._entries[pool_key].append(entry)
                logger.debug("Registered session %s for scheduling", session.session_id)

    async def unregister_session(
        self, exchange_id: str, session_type: SessionType, session_id: str
    ) -> bool:
        """Remove a session from scheduling."""
        pool_key = f"{exchange_id}_{session_type.value}"
        async with self._lock:
            if pool_key not in self._entries:
                return False
            before = len(self._entries[pool_key])
            self._entries[pool_key] = [
                e for e in self._entries[pool_key]
                if e.session.session_id != session_id
            ]
            return len(self._entries[pool_key]) < before

    # ---- Selection ----

    async def select(
        self, exchange_id: str, session_type: SessionType
    ) -> Optional[ExchangeSession]:
        """Select the best session based on scheduling policy."""
        pool_key = f"{exchange_id}_{session_type.value}"
        entries = self._entries.get(pool_key, [])

        if not entries:
            return None

        # Filter to only connected sessions
        active = [e for e in entries if e.session.is_connected]
        if not active:
            return None

        selected_entry = self._apply_policy(active, pool_key)
        if selected_entry:
            selected_entry.current_load += 1
            return selected_entry.session
        return None

    async def release(
        self, exchange_id: str, session_type: SessionType, session_id: str
    ) -> None:
        """Release a session (decrease load count)."""
        pool_key = f"{exchange_id}_{session_type.value}"
        for entry in self._entries.get(pool_key, []):
            if entry.session.session_id == session_id:
                entry.current_load = max(0, entry.current_load - 1)
                break

    async def update_rate_limit(
        self, exchange_id: str, session_type: SessionType,
        session_id: str, remaining: float,
    ) -> None:
        """Update rate limit remaining for a session."""
        pool_key = f"{exchange_id}_{session_type.value}"
        for entry in self._entries.get(pool_key, []):
            if entry.session.session_id == session_id:
                entry.rate_limit_remaining = remaining
                break

    # ---- Policy Implementation ----

    def _apply_policy(
        self, entries: list[ScheduleEntry], pool_key: str
    ) -> Optional[ScheduleEntry]:
        """Apply the scheduling policy to select an entry."""
        if self.policy == SchedulePolicy.ROUND_ROBIN:
            return self._round_robin_select(entries, pool_key)
        elif self.policy == SchedulePolicy.LEAST_LOADED:
            return self._least_loaded_select(entries)
        elif self.policy == SchedulePolicy.PRIORITY:
            return self._priority_select(entries)
        elif self.policy == SchedulePolicy.RATE_LIMIT_AWARE:
            return self._rate_limit_aware_select(entries)
        elif self.policy == SchedulePolicy.LATENCY_OPTIMIZED:
            return self._latency_optimized_select(entries)
        return entries[0] if entries else None

    def _round_robin_select(
        self, entries: list[ScheduleEntry], pool_key: str
    ) -> Optional[ScheduleEntry]:
        """Round-robin selection."""
        idx = self._round_robin_index.get(pool_key, 0)
        entry = entries[idx % len(entries)]
        self._round_robin_index[pool_key] = (idx + 1) % len(entries)
        return entry

    @staticmethod
    def _least_loaded_select(entries: list[ScheduleEntry]) -> Optional[ScheduleEntry]:
        """Select the entry with the lowest current load."""
        return min(entries, key=lambda e: e.current_load)

    @staticmethod
    def _priority_select(entries: list[ScheduleEntry]) -> Optional[ScheduleEntry]:
        """Select the entry with the highest priority."""
        return max(entries, key=lambda e: e.priority)

    @staticmethod
    def _rate_limit_aware_select(entries: list[ScheduleEntry]) -> Optional[ScheduleEntry]:
        """Select the entry with the most remaining rate limit capacity."""
        return max(entries, key=lambda e: e.rate_limit_remaining)

    @staticmethod
    def _latency_optimized_select(entries: list[ScheduleEntry]) -> Optional[ScheduleEntry]:
        """Select the entry with the lowest recent latency."""
        return min(
            entries,
            key=lambda e: e.session.metadata.get("avg_latency_ms", 999999.0),
        )

    # ---- Status ----

    async def get_status(self) -> dict[str, Any]:
        """Get scheduler status."""
        total_entries = sum(len(entries) for entries in self._entries.values())
        pools = {}
        for key, entries in self._entries.items():
            active = sum(1 for e in entries if e.session.is_connected)
            total_load = sum(e.current_load for e in entries)
            pools[key] = {
                "total": len(entries),
                "active": active,
                "total_load": total_load,
            }

        return {
            "policy": self.policy.value,
            "total_entries": total_entries,
            "pools": pools,
        }
