"""Fair Share Scheduler — prevents resource starvation across tenants.

The :class:`FairShareScheduler` ensures each tenant gets its proportional
share of cluster resources, even when other tenants are submitting many
jobs.  Uses weighted fair queuing (WFQ) principles.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FairShareResult:
    """Result of fair-share allocation calculation."""

    tenant_id: str
    weight: float
    target_share: float  # desired fraction 0.0–1.0
    actual_share: float  # current fraction
    cpu_allocated: float
    memory_allocated_mb: float
    job_count: int
    is_starving: bool = False


class FairShareScheduler:
    """Weighted fair-share scheduler to prevent resource starvation.

    Usage::

        fair = FairShareScheduler()
        fair.set_tenant_weight("quant-a", 2.0)   # double share
        fair.set_tenant_weight("quant-b", 1.0)
        result = fair.calculate_shares({"quant-a": (4, 8192, 5), "quant-b": (1, 2048, 1)})
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._weights: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Weight management
    # ------------------------------------------------------------------

    def set_tenant_weight(self, tenant_id: str, weight: float) -> None:
        with self._lock:
            self._weights[tenant_id] = max(0.0, weight)

    def remove_tenant(self, tenant_id: str) -> None:
        with self._lock:
            self._weights.pop(tenant_id, None)

    # ------------------------------------------------------------------
    # Calculation
    # ------------------------------------------------------------------

    def calculate_shares(
        self, usage: Dict[str, Tuple[float, float, int]],
    ) -> List[FairShareResult]:
        """Calculate fair-share allocation for all tenants.

        Args:
            usage: tenant_id → (cpu_used, memory_mb_used, job_count)

        Returns:
            List of FairShareResult, one per tenant.
        """
        with self._lock:
            if not usage:
                return []

            # Default weight = 1.0 for tenants without explicit weight
            total_weight = sum(
                self._weights.get(tid, 1.0) for tid in usage
            )
            if total_weight <= 0:
                total_weight = len(usage)

            results = []
            for tid, (cpu, mem, jobs) in usage.items():
                weight = self._weights.get(tid, 1.0)
                target = weight / total_weight
                actual = cpu / max(sum(u[0] for u in usage.values()), 0.001)

                results.append(FairShareResult(
                    tenant_id=tid,
                    weight=weight,
                    target_share=target,
                    actual_share=actual,
                    cpu_allocated=cpu,
                    memory_allocated_mb=mem,
                    job_count=jobs,
                    is_starving=actual < target * 0.5,  # < 50% of target
                ))

            return sorted(results, key=lambda r: r.actual_share)

    def get_victim(
        self, usage: Dict[str, Tuple[float, float, int]],
    ) -> Optional[str]:
        """Identify the tenant using more than its fair share (preemption victim)."""
        results = self.calculate_shares(usage)
        if not results:
            return None

        # Tenant using the most relative to its fair share
        max_overuse = 0.0
        victim: Optional[str] = None
        for r in results:
            overuse = r.actual_share - r.target_share
            if overuse > max_overuse and r.job_count > 0:
                max_overuse = overuse
                victim = r.tenant_id

        return victim

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "tenants": len(self._weights),
                "weights": dict(self._weights),
            }
