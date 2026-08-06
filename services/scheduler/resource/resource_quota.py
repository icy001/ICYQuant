"""Resource Quota — enforces per-tenant resource limits.

The :class:`ResourceQuota` prevents any single tenant, strategy, or
workflow from monopolizing cluster resources.  Supports soft and hard
limits with configurable overcommit ratios.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class QuotaLimit:
    """Resource limits for a tenant."""

    tenant_id: str
    max_cpu: float = float("inf")
    max_memory_mb: float = float("inf")
    max_gpu: float = float("inf")
    max_concurrent_jobs: int = 100
    overcommit_ratio: float = 1.0  # allow overcommit up to ratio*limit in soft mode
    is_hard: bool = True


class ResourceQuota:
    """Per-tenant resource quota enforcement.

    Usage::

        quota = ResourceQuota()
        quota.set_quota("tenant-a", max_cpu=16, max_memory_mb=32768)
        ok = quota.check("tenant-a", cpu_request=4)  # True
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._limits: Dict[str, QuotaLimit] = {}
        self._usage: Dict[str, Dict[str, float]] = {}  # tenant → {cpu, memory, gpu, jobs}

    # ------------------------------------------------------------------
    # Quota management
    # ------------------------------------------------------------------

    def set_quota(
        self, tenant_id: str, max_cpu: float = float("inf"),
        max_memory_mb: float = float("inf"), max_gpu: float = float("inf"),
        max_concurrent_jobs: int = 100, overcommit_ratio: float = 1.0,
        is_hard: bool = True,
    ) -> None:
        with self._lock:
            self._limits[tenant_id] = QuotaLimit(
                tenant_id=tenant_id, max_cpu=max_cpu,
                max_memory_mb=max_memory_mb, max_gpu=max_gpu,
                max_concurrent_jobs=max_concurrent_jobs,
                overcommit_ratio=overcommit_ratio, is_hard=is_hard,
            )
            if tenant_id not in self._usage:
                self._usage[tenant_id] = {"cpu": 0.0, "memory_mb": 0.0, "gpu": 0.0, "jobs": 0}

    def remove_quota(self, tenant_id: str) -> None:
        with self._lock:
            self._limits.pop(tenant_id, None)
            self._usage.pop(tenant_id, None)

    # ------------------------------------------------------------------
    # Check
    # ------------------------------------------------------------------

    def check(
        self, tenant_id: str, cpu_request: float = 0.0,
        memory_mb_request: float = 0.0, gpu_request: float = 0.0,
    ) -> bool:
        """Check if a resource request fits within the tenant's quota.

        Returns False if the request would exceed the quota.
        """
        with self._lock:
            limit = self._limits.get(tenant_id)
            if limit is None:
                return True  # No quota defined → unrestricted

            usage = self._usage.get(tenant_id, {"cpu": 0.0, "memory_mb": 0.0, "gpu": 0.0, "jobs": 0})

            effective_limit_cpu = limit.max_cpu * limit.overcommit_ratio
            effective_limit_mem = limit.max_memory_mb * limit.overcommit_ratio

            if limit.is_hard:
                if usage["cpu"] + cpu_request > limit.max_cpu:
                    return False
                if usage["memory_mb"] + memory_mb_request > limit.max_memory_mb:
                    return False
                if usage["gpu"] + gpu_request > limit.max_gpu:
                    return False
            else:
                if usage["cpu"] + cpu_request > effective_limit_cpu:
                    return False
                if usage["memory_mb"] + memory_mb_request > effective_limit_mem:
                    return False

            if usage["jobs"] + 1 > limit.max_concurrent_jobs:
                return False

            return True

    # ------------------------------------------------------------------
    # Usage tracking
    # ------------------------------------------------------------------

    def reserve(self, tenant_id: str, cpu: float, memory_mb: float, gpu: float = 0.0) -> None:
        with self._lock:
            if tenant_id not in self._usage:
                self._usage[tenant_id] = {"cpu": 0.0, "memory_mb": 0.0, "gpu": 0.0, "jobs": 0}
            self._usage[tenant_id]["cpu"] += cpu
            self._usage[tenant_id]["memory_mb"] += memory_mb
            self._usage[tenant_id]["gpu"] += gpu
            self._usage[tenant_id]["jobs"] += 1

    def release(self, tenant_id: str, cpu: float, memory_mb: float, gpu: float = 0.0) -> None:
        with self._lock:
            usage = self._usage.get(tenant_id)
            if usage is None:
                return
            usage["cpu"] = max(0.0, usage["cpu"] - cpu)
            usage["memory_mb"] = max(0.0, usage["memory_mb"] - memory_mb)
            usage["gpu"] = max(0.0, usage["gpu"] - gpu)
            usage["jobs"] = max(0, usage["jobs"] - 1)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_usage(self, tenant_id: str) -> Dict[str, float]:
        with self._lock:
            return dict(self._usage.get(tenant_id, {"cpu": 0.0, "memory_mb": 0.0, "gpu": 0.0, "jobs": 0}))

    def get_limit(self, tenant_id: str) -> Optional[QuotaLimit]:
        with self._lock:
            return self._limits.get(tenant_id)

    def list_quotas(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {
                tid: {
                    "limit": {
                        "max_cpu": l.max_cpu, "max_memory_mb": l.max_memory_mb,
                        "max_gpu": l.max_gpu, "max_concurrent_jobs": l.max_concurrent_jobs,
                        "is_hard": l.is_hard,
                    },
                    "usage": self._usage.get(tid, {}),
                }
                for tid, l in self._limits.items()
            }

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "tenants_with_quota": len(self._limits),
                "tenants_over_quota": sum(
                    1 for tid, l in self._limits.items()
                    if self._usage.get(tid, {}).get("cpu", 0) > l.max_cpu
                ),
            }
