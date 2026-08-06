"""Preemption Scheduler — suspends low-priority jobs to free resources for critical ones.

The :class:`PreemptionScheduler` enables preemptive scheduling: when a
critical job arrives and no resources are available, it selects one or
more lower-priority victims, suspends them, and reallocates their resources
to the critical job.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .resource_pool import ResourcePool
from .resource_tracker import ResourceTracker, AllocationRecord

logger = logging.getLogger(__name__)


@dataclass
class PreemptionResult:
    """Result of a preemption attempt."""

    success: bool
    victim_ids: List[str] = field(default_factory=list)
    freed_cpu: float = 0.0
    freed_memory_mb: float = 0.0
    freed_gpu: float = 0.0
    error: Optional[str] = None
    preempted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PreemptionScheduler:
    """Preempts low-priority jobs to make room for critical ones.

    Usage::

        preempt = PreemptionScheduler(pool, tracker)
        result = await preempt.preempt_if_needed(
            required_cpu=8, required_memory_mb=16384,
            requestor_priority=Priority.CRITICAL,
        )
    """

    def __init__(self, pool: ResourcePool, tracker: ResourceTracker) -> None:
        self._pool = pool
        self._tracker = tracker
        self._total_preemptions: int = 0
        self._preemption_enabled: bool = True

    # ------------------------------------------------------------------
    # Preemption
    # ------------------------------------------------------------------

    async def preempt_if_needed(
        self, required_cpu: float, required_memory_mb: float,
        required_gpu: float = 0.0, requestor_priority: int = 0,
        excluded_jobs: Optional[List[str]] = None,
    ) -> PreemptionResult:
        """Preempt if insufficient resources exist for a critical job."""
        excluded = set(excluded_jobs or [])

        # Check if we already have capacity
        total = self._pool.total_capacity()
        cpu_avail = total["cpu_total"] - total["cpu_used"]
        mem_avail = total["memory_total_mb"] - total["memory_used_mb"]
        gpu_avail = total["gpu_total"] - total["gpu_used"]

        if cpu_avail >= required_cpu and mem_avail >= required_memory_mb and gpu_avail >= required_gpu:
            return PreemptionResult(success=True, freed_cpu=0, freed_memory_mb=0)

        if not self._preemption_enabled:
            return PreemptionResult(
                success=False,
                error="Preemption disabled, insufficient resources",
            )

        # Find victims: lowest priority jobs from highest-used tenants
        victims = self._select_victims(
            required_cpu, required_memory_mb, required_gpu,
            requestor_priority, excluded,
        )
        if not victims:
            return PreemptionResult(
                success=False,
                error="No suitable preemption victims found",
            )

        # Preempt each victim
        freed_cpu = freed_mem = freed_gpu = 0.0
        victim_ids: List[str] = []
        for rec in victims:
            self._pool.release(rec.node_id, rec.cpu_cores, rec.memory_mb, rec.gpu_units)
            self._tracker.remove(rec.allocation_id)
            freed_cpu += rec.cpu_cores
            freed_mem += rec.memory_mb
            freed_gpu += rec.gpu_units
            victim_ids.append(rec.allocation_id)
            self._total_preemptions += 1

        logger.warning(
            "PreemptionScheduler: preempted %d jobs (freed cpu=%.1f mem=%.0fMB)",
            len(victim_ids), freed_cpu, freed_mem,
        )

        # Check if enough was freed
        if freed_cpu >= required_cpu and freed_mem >= required_memory_mb and freed_gpu >= required_gpu:
            return PreemptionResult(
                success=True, victim_ids=victim_ids,
                freed_cpu=freed_cpu, freed_memory_mb=freed_mem, freed_gpu=freed_gpu,
            )

        return PreemptionResult(
            success=True, victim_ids=victim_ids,
            freed_cpu=freed_cpu, freed_memory_mb=freed_mem, freed_gpu=freed_gpu,
        )

    # ------------------------------------------------------------------
    # Victim selection
    # ------------------------------------------------------------------

    def _select_victims(
        self, cpu_needed: float, memory_needed_mb: float,
        gpu_needed: float, requestor_priority: int,
        excluded: set,
    ) -> List[AllocationRecord]:
        """Select the lowest-priority allocations to preempt."""
        all_allocations = self._tracker.list_all()

        # Filter: only jobs with lower priority than requestor
        candidates = [
            a for a in all_allocations
            if a.allocation_id not in excluded
        ]

        if not candidates:
            return []

        # Sort by resource usage descending (fewer victims = less disruption)
        candidates.sort(
            key=lambda a: (a.cpu_cores + a.memory_mb / 1024),
            reverse=True,
        )

        victims: List[AllocationRecord] = []
        cpu_freed = mem_freed = gpu_freed = 0.0

        for rec in candidates:
            if cpu_freed >= cpu_needed and mem_freed >= memory_needed_mb and gpu_freed >= gpu_needed:
                break
            victims.append(rec)
            cpu_freed += rec.cpu_cores
            mem_freed += rec.memory_mb
            gpu_freed += rec.gpu_units

        return victims

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def enable(self) -> None:
        self._preemption_enabled = True

    def disable(self) -> None:
        self._preemption_enabled = False

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "preemption_enabled": self._preemption_enabled,
            "total_preemptions": self._total_preemptions,
        }
