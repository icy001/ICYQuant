"""Resource model — tracks and allocates scheduling resources."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ResourceUnit(str, enum.Enum):
    """Unit of resource measurement."""

    CPU_CORES = "cpu_cores"
    MEMORY_MB = "memory_mb"
    DISK_GB = "disk_gb"
    GPU_UNITS = "gpu_units"
    QUEUE_SLOTS = "queue_slots"
    CONCURRENCY = "concurrency"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ResourceSpec:
    """Immutable resource specification for a single dimension."""

    name: str
    unit: ResourceUnit
    capacity: float
    allocated: float = 0.0
    reserved: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)

    @property
    def available(self) -> float:
        """Remaining available capacity."""
        return max(0.0, self.capacity - self.allocated - self.reserved)

    @property
    def utilization_pct(self) -> float:
        """Percentage of capacity in use."""
        if self.capacity <= 0:
            return 100.0
        return (self.allocated / self.capacity) * 100.0

    def can_allocate(self, amount: float) -> bool:
        """Check if the requested amount can be allocated."""
        return self.available >= amount


@dataclass(frozen=True)
class ResourceRequirement:
    """Immutable resource requirements for a job or schedule."""

    requirements: Dict[str, float] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def get(self, resource_name: str, default: float = 0.0) -> float:
        """Get required amount for a resource."""
        return self.requirements.get(resource_name, default)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "requirements": self.requirements,
            "labels": self.labels,
            "tags": self.tags,
        }


@dataclass(frozen=True)
class ResourcePool:
    """Immutable resource pool tracked per worker or cluster-wide."""

    pool_id: str
    name: str
    resources: Dict[str, ResourceSpec] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def can_satisfy(self, requirement: ResourceRequirement) -> bool:
        """Check if all requirements can be satisfied by this pool."""
        for name, amount in requirement.requirements.items():
            spec = self.resources.get(name)
            if spec is None:
                return False
            if not spec.can_allocate(amount):
                return False
        return True

    def total_utilization(self) -> float:
        """Aggregate utilization across all resources."""
        if not self.resources:
            return 0.0
        utils = [r.utilization_pct for r in self.resources.values()]
        return sum(utils) / len(utils)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "pool_id": self.pool_id,
            "name": self.name,
            "resources": {
                k: {
                    "capacity": v.capacity,
                    "allocated": v.allocated,
                    "reserved": v.reserved,
                    "available": v.available,
                    "utilization_pct": v.utilization_pct,
                    "unit": v.unit.value,
                }
                for k, v in self.resources.items()
            },
            "labels": self.labels,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
