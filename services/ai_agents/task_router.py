"""
ICYQuant Task Router — capability-based task dispatch to agents.

Matches incoming tasks to the most suitable agents based on capability
requirements, agent availability, load, and performance history.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DispatchStrategy(str, Enum):
    BEST_MATCH = "best_match"       # Highest capability overlap
    LEAST_LOADED = "least_loaded"   # Lowest current task count
    ROUND_ROBIN = "round_robin"     # Even distribution
    PRIORITY_FIRST = "priority_first"  # Priority-aware dispatch
    AFFINITY = "affinity"           # Route to same agent as before


@dataclass
class DispatchResult:
    """Result of a task dispatch attempt."""
    task_id: str
    agent_id: str = ""
    success: bool = False
    strategy: DispatchStrategy = DispatchStrategy.BEST_MATCH
    reason: str = ""
    dispatched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RouterStats:
    tasks_received: int = 0
    tasks_dispatched: int = 0
    tasks_failed: int = 0
    tasks_queued: int = 0
    avg_wait_ms: float = 0.0


class TaskRouter:
    """Routes tasks to agents based on capability matching and load.

    Features:
        - Multi-strategy dispatch (best-match, least-loaded, round-robin, affinity)
        - Capability-based agent selection
        - Load-aware routing with task count and queue depth
        - Fallback dispatch when primary agent is unavailable
        - Affinity routing for stateful tasks
        - Circuit breaker for failing agents
    """

    def __init__(self, registry: Any = None, scheduler: Any = None,
                 default_strategy: DispatchStrategy = DispatchStrategy.BEST_MATCH) -> None:
        self._registry = registry
        self._scheduler = scheduler
        self._default_strategy = default_strategy

        # Per-task-type affinity: task_type → preferred agent_id
        self._affinity_map: dict[str, str] = {}

        # Circuit breaker: agent_id → (failure_count, last_failure_time, open)
        self._circuit_breakers: dict[str, tuple[int, float, bool]] = {}

        self._round_robin_index: dict[str, int] = {}
        self._stats = RouterStats()
        self._lock = asyncio.Lock()

    # ── Main Dispatch ──

    async def dispatch(self, task_id: str, required_capabilities: list[str],
                       description: str = "",
                       strategy: Optional[DispatchStrategy] = None,
                       preferred_agent: str = "",
                       metadata: Optional[dict[str, Any]] = None) -> DispatchResult:
        """Dispatch a task to the best available agent."""
        self._stats.tasks_received += 1
        strategy = strategy or self._default_strategy

        agent_id = await self._select_agent(strategy, required_capabilities, preferred_agent)

        result = DispatchResult(task_id=task_id, strategy=strategy)

        if not agent_id:
            # No agent found — queue for later
            self._stats.tasks_queued += 1
            result.reason = "No available agent found"
            return result

        # Check circuit breaker
        if self._is_circuit_open(agent_id):
            self._stats.tasks_failed += 1
            result.reason = f"Circuit breaker open for {agent_id}"
            logger.warning("Circuit breaker blocking dispatch to %s", agent_id)
            return result

        # Try to assign via scheduler
        if self._scheduler:
            task = self._scheduler.schedule(
                task_id=task_id,
                description=description,
                required_capabilities=required_capabilities,
                metadata=metadata,
            )
            assigned = self._scheduler.assign_task(task_id, agent_id)
            if not assigned:
                self._stats.tasks_failed += 1
                result.reason = "Scheduler assignment failed"
                return result

        result.agent_id = agent_id
        result.success = True
        self._stats.tasks_dispatched += 1
        logger.info("Dispatched task %s → %s [%s]", task_id, agent_id, strategy.value)
        return result

    # ── Agent Selection ──

    async def _select_agent(self, strategy: DispatchStrategy,
                            required_capabilities: list[str],
                            preferred_agent: str) -> Optional[str]:
        """Select the best agent using the given strategy."""
        if strategy == DispatchStrategy.AFFINITY:
            return self._affinity_select(required_capabilities, preferred_agent)
        elif strategy == DispatchStrategy.BEST_MATCH:
            return self._best_match_select(required_capabilities)
        elif strategy == DispatchStrategy.LEAST_LOADED:
            return self._least_loaded_select(required_capabilities)
        elif strategy == DispatchStrategy.ROUND_ROBIN:
            return self._round_robin_select(required_capabilities)
        elif strategy == DispatchStrategy.PRIORITY_FIRST:
            return self._best_match_select(required_capabilities)  # Same logic for now
        return None

    def _best_match_select(self, required_capabilities: list[str]) -> Optional[str]:
        """Select agent with highest capability overlap score."""
        if self._scheduler:
            agent_id = self._scheduler.find_best_agent(required_capabilities)
            if agent_id and not self._is_circuit_open(agent_id):
                return agent_id

        if self._registry is None:
            return None

        best_agent: Optional[str] = None
        best_score = -1.0
        required = set(required_capabilities)

        for agent_info in self._registry.list_all():
            agent_id = agent_info.agent_id if hasattr(agent_info, 'agent_id') else str(agent_info)
            if self._is_circuit_open(agent_id):
                continue

            caps = set(getattr(agent_info, 'capabilities', []))
            if required and not required.issubset(caps):
                continue

            overlap = len(required & caps) if required else len(caps)
            load = getattr(agent_info, 'task_count', 0)
            score = overlap - (load * 0.15)
            if score > best_score:
                best_score = score
                best_agent = agent_id

        return best_agent

    def _least_loaded_select(self, required_capabilities: list[str]) -> Optional[str]:
        """Select agent with lowest current task load."""
        if self._registry is None:
            return None

        best_agent: Optional[str] = None
        min_load = float('inf')
        required = set(required_capabilities)

        for agent_info in self._registry.list_all():
            agent_id = agent_info.agent_id if hasattr(agent_info, 'agent_id') else str(agent_info)
            if self._is_circuit_open(agent_id):
                continue

            caps = set(getattr(agent_info, 'capabilities', []))
            if required and not required.issubset(caps):
                continue

            load = getattr(agent_info, 'task_count', 0)
            if load < min_load:
                min_load = load
                best_agent = agent_id

        return best_agent

    def _round_robin_select(self, required_capabilities: list[str]) -> Optional[str]:
        """Select agents in round-robin order."""
        if self._registry is None:
            return None

        candidates = []
        for agent_info in self._registry.list_all():
            agent_id = agent_info.agent_id if hasattr(agent_info, 'agent_id') else str(agent_info)
            if self._is_circuit_open(agent_id):
                continue
            caps = set(getattr(agent_info, 'capabilities', []))
            if not required or set(required_capabilities).issubset(caps):
                candidates.append(agent_id)

        if not candidates:
            return None

        key = ",".join(sorted(required_capabilities)) if required_capabilities else "all"
        idx = self._round_robin_index.get(key, 0)
        agent_id = candidates[idx % len(candidates)]
        self._round_robin_index[key] = idx + 1
        return agent_id

    def _affinity_select(self, required_capabilities: list[str],
                         preferred_agent: str) -> Optional[str]:
        """Select based on affinity, with fallback to best match."""
        if preferred_agent and not self._is_circuit_open(preferred_agent):
            return preferred_agent

        cap_key = ",".join(sorted(required_capabilities))
        cached = self._affinity_map.get(cap_key)
        if cached and not self._is_circuit_open(cached):
            return cached

        return self._best_match_select(required_capabilities)

    # ── Affinity Management ──

    def set_affinity(self, task_type: str, agent_id: str) -> None:
        """Set affinity so future tasks of this type go to the same agent."""
        self._affinity_map[task_type] = agent_id

    def clear_affinity(self, task_type: str) -> None:
        self._affinity_map.pop(task_type, None)

    # ── Circuit Breaker ──

    def record_failure(self, agent_id: str) -> None:
        """Record a failure for circuit breaker tracking."""
        loop = asyncio.get_event_loop()
        now = loop.time()
        count, last_time, _ = self._circuit_breakers.get(agent_id, (0, 0, False))

        if now - last_time > 60:  # Reset counter after 60s
            count = 0

        count += 1
        is_open = count >= 5  # Open after 5 consecutive failures
        self._circuit_breakers[agent_id] = (count, now, is_open)

        if is_open:
            logger.warning("Circuit breaker OPEN for agent %s (%d failures)", agent_id, count)

    def reset_circuit_breaker(self, agent_id: str) -> None:
        """Reset the circuit breaker for an agent."""
        self._circuit_breakers.pop(agent_id, None)

    def _is_circuit_open(self, agent_id: str) -> bool:
        cb = self._circuit_breakers.get(agent_id)
        if cb is None:
            return False
        count, last_time, is_open = cb
        if is_open:
            now = asyncio.get_event_loop().time()
            if now - last_time > 120:  # Half-open after 120s
                self._circuit_breakers[agent_id] = (count, last_time, False)
                return False
            return True
        return False

    # ── Stats ──

    @property
    def stats(self) -> RouterStats:
        return self._stats
