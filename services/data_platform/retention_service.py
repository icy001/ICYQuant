"""
ICYQuant Retention Service.

Commit 16 Part 1.5 — Data retention policy management service.
Manages data lifecycle from hot storage through warm/cold tiers to
archive and eventual deletion, optimizing cost and compliance.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StorageTier(str, Enum):
    """Data storage tiers."""
    HOT = "hot"           # Frequently accessed, fastest storage
    WARM = "warm"         # Less frequent, moderate cost
    COLD = "cold"         # Rarely accessed, lowest cost
    ARCHIVE = "archive"   # Compliance/backup only
    DELETED = "deleted"   # Permanently removed


class RetentionAction(str, Enum):
    """Actions to take based on retention policy."""
    KEEP = "keep"
    MOVE_TO_WARM = "move_to_warm"
    MOVE_TO_COLD = "move_to_cold"
    ARCHIVE = "archive"
    DELETE = "delete"
    SNAPSHOT = "snapshot"


@dataclass
class RetentionPolicy:
    """A data retention policy."""
    policy_id: str = ""
    dataset_id: str = ""
    name: str = ""
    description: str = ""
    hot_retention_days: int = 30
    warm_retention_days: int = 90
    cold_retention_days: int = 365
    archive_days: int = 2555    # 7 years default for compliance
    auto_delete: bool = True
    min_snapshots: int = 1
    max_snapshots: int = 10
    snapshot_schedule: str = ""  # cron expression
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetentionStatus:
    """Current retention status for a dataset."""
    dataset_id: str = ""
    current_tier: StorageTier = StorageTier.HOT
    days_in_current_tier: int = 0
    snapshot_count: int = 0
    oldest_snapshot_age_days: int = 0
    next_action: RetentionAction = RetentionAction.KEEP
    next_action_date: Optional[datetime] = None
    total_size_bytes: int = 0
    estimated_monthly_cost: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetentionReport:
    """Aggregated retention report."""
    generated_at: Optional[datetime] = None
    total_datasets: int = 0
    datasets_with_policy: int = 0
    upcoming_actions: list[RetentionStatus] = field(default_factory=list)
    estimated_savings_monthly: float = 0.0
    archived_datasets: int = 0
    deleted_datasets: int = 0


class RetentionService:
    """Data retention policy management service.

    Manages the full data lifecycle:
      Hot (0-30 days) → Warm (30-90 days) → Cold (90-365 days) →
      Archive (365-2555 days) → Delete

    Provides:
      - Tiered retention policy management
      - Automated lifecycle transitions
      - Snapshot scheduling
      - Cost estimation
      - Compliance reporting
    """

    # Storage cost per GB per month (example estimates)
    TIER_COST_PER_GB: dict[StorageTier, float] = {
        StorageTier.HOT: 0.023,
        StorageTier.WARM: 0.0125,
        StorageTier.COLD: 0.004,
        StorageTier.ARCHIVE: 0.001,
        StorageTier.DELETED: 0.0,
    }

    def __init__(self) -> None:
        self._policies: dict[str, RetentionPolicy] = {}
        self._statuses: dict[str, RetentionStatus] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Policy Management
    # ------------------------------------------------------------------

    async def create_policy(self, policy: RetentionPolicy) -> str:
        """Create a retention policy."""
        async with self._lock:
            policy.created_at = policy.created_at or datetime.now(timezone.utc)
            policy.updated_at = policy.created_at
            self._policies[policy.policy_id] = policy
        logger.info("Retention policy created: %s (dataset=%s)", policy.policy_id, policy.dataset_id)
        return policy.policy_id

    async def get_policy(self, policy_id: str) -> Optional[RetentionPolicy]:
        """Get a policy by ID."""
        return self._policies.get(policy_id)

    async def get_dataset_policy(self, dataset_id: str) -> Optional[RetentionPolicy]:
        """Get the retention policy for a dataset."""
        for policy in self._policies.values():
            if policy.dataset_id == dataset_id:
                return policy
        return None

    async def list_policies(self) -> list[RetentionPolicy]:
        """List all retention policies."""
        return list(self._policies.values())

    async def update_policy(self, policy_id: str, **kwargs: Any) -> bool:
        """Update a retention policy."""
        async with self._lock:
            policy = self._policies.get(policy_id)
            if not policy:
                return False
            for key, value in kwargs.items():
                if hasattr(policy, key):
                    setattr(policy, key, value)
            policy.updated_at = datetime.now(timezone.utc)
            return True

    # ------------------------------------------------------------------
    # Lifecycle Evaluation
    # ------------------------------------------------------------------

    async def evaluate(self, dataset_id: str, creation_date: datetime) -> RetentionAction:
        """Determine the retention action for a dataset based on its age."""
        policy = await self.get_dataset_policy(dataset_id)
        if not policy or not policy.enabled:
            return RetentionAction.KEEP

        age_days = (datetime.now(timezone.utc) - creation_date).days

        if age_days >= policy.archive_days:
            return RetentionAction.DELETE if policy.auto_delete else RetentionAction.ARCHIVE
        if age_days >= policy.cold_retention_days:
            return RetentionAction.ARCHIVE
        if age_days >= policy.warm_retention_days:
            return RetentionAction.MOVE_TO_COLD
        if age_days >= policy.hot_retention_days:
            return RetentionAction.MOVE_TO_WARM

        return RetentionAction.KEEP

    async def evaluate_all(self) -> RetentionReport:
        """Evaluate retention for all managed datasets."""
        report = RetentionReport(generated_at=datetime.now(timezone.utc))
        report.total_datasets = len(self._policies)
        report.datasets_with_policy = sum(1 for p in self._policies.values() if p.enabled)

        for policy in self._policies.values():
            if not policy.enabled:
                continue
            status = await self.get_status(policy.dataset_id)
            if status and status.next_action != RetentionAction.KEEP:
                report.upcoming_actions.append(status)
                report.estimated_savings_monthly += status.estimated_monthly_cost

        return report

    async def get_status(self, dataset_id: str) -> Optional[RetentionStatus]:
        """Get current retention status for a dataset."""
        status = self._statuses.get(dataset_id)
        if not status:
            return None

        age = (datetime.now(timezone.utc) - datetime.now(timezone.utc)).days  # placeholder
        status.days_in_current_tier = age
        status.next_action = await self.evaluate(dataset_id, datetime.now(timezone.utc) - timedelta(days=age))
        return status

    async def estimate_cost(self, dataset_id: str, size_gb: float) -> float:
        """Estimate monthly storage cost for a dataset."""
        policy = await self.get_dataset_policy(dataset_id)
        if not policy:
            return size_gb * self.TIER_COST_PER_GB[StorageTier.HOT]

        # Weighted cost across tiers
        total_days = policy.hot_retention_days + policy.warm_retention_days + policy.cold_retention_days
        if total_days == 0:
            return size_gb * self.TIER_COST_PER_GB[StorageTier.HOT]

        hot_weight = policy.hot_retention_days / total_days
        warm_weight = policy.warm_retention_days / total_days
        cold_weight = policy.cold_retention_days / total_days

        return size_gb * (
            hot_weight * self.TIER_COST_PER_GB[StorageTier.HOT]
            + warm_weight * self.TIER_COST_PER_GB[StorageTier.WARM]
            + cold_weight * self.TIER_COST_PER_GB[StorageTier.COLD]
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def policy_count(self) -> int:
        return len(self._policies)
