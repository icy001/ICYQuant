"""Metadata model — structured metadata for schedules, jobs, and executions."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class MetadataKey(str, enum.Enum):
    """Canonical metadata keys."""

    OWNER = "owner"
    TEAM = "team"
    ENVIRONMENT = "environment"
    VERSION = "version"
    REGION = "region"
    CLUSTER = "cluster"
    DOMAIN = "domain"
    TENANT = "tenant"
    PIPELINE = "pipeline"
    COST_CENTER = "cost_center"
    COMPLIANCE = "compliance"


@dataclass(frozen=True)
class ScheduleMetadata:
    """Immutable metadata for a schedule definition."""

    schedule_id: str
    owner: str = ""
    team: str = ""
    environment: str = ""
    region: str = ""
    cluster: str = ""
    domain: str = ""
    tenant: str = ""
    cost_center: str = ""
    compliance_tags: List[str] = field(default_factory=list)
    custom: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def get(self, key: MetadataKey, default: str = "") -> str:
        """Get a canonical metadata value."""
        mapping = {
            MetadataKey.OWNER: self.owner,
            MetadataKey.TEAM: self.team,
            MetadataKey.ENVIRONMENT: self.environment,
            MetadataKey.REGION: self.region,
            MetadataKey.CLUSTER: self.cluster,
            MetadataKey.DOMAIN: self.domain,
            MetadataKey.TENANT: self.tenant,
            MetadataKey.COST_CENTER: self.cost_center,
        }
        return mapping.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "schedule_id": self.schedule_id,
            "owner": self.owner,
            "team": self.team,
            "environment": self.environment,
            "region": self.region,
            "cluster": self.cluster,
            "domain": self.domain,
            "tenant": self.tenant,
            "cost_center": self.cost_center,
            "compliance_tags": self.compliance_tags,
            "custom": self.custom,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass(frozen=True)
class JobMetadata:
    """Immutable metadata for a job instance."""

    job_id: str
    schedule_id: str
    execution_count: int = 0
    last_execution_id: Optional[str] = None
    last_state: Optional[str] = None
    last_duration_ms: Optional[float] = None
    total_duration_ms: float = 0.0
    total_failures: int = 0
    total_successes: int = 0
    labels: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "job_id": self.job_id,
            "schedule_id": self.schedule_id,
            "execution_count": self.execution_count,
            "last_execution_id": self.last_execution_id,
            "last_state": self.last_state,
            "last_duration_ms": self.last_duration_ms,
            "total_duration_ms": self.total_duration_ms,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "labels": self.labels,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass(frozen=True)
class ExecutionMetadata:
    """Immutable metadata for an execution record."""

    execution_id: str
    job_id: str
    schedule_id: str
    trigger_type: str = ""
    worker_id: Optional[str] = None
    trace_id: Optional[str] = None
    attempt: int = 1
    labels: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    custom: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "execution_id": self.execution_id,
            "job_id": self.job_id,
            "schedule_id": self.schedule_id,
            "trigger_type": self.trigger_type,
            "worker_id": self.worker_id,
            "trace_id": self.trace_id,
            "attempt": self.attempt,
            "labels": self.labels,
            "tags": self.tags,
            "custom": self.custom,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
