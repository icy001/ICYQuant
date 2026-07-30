"""ICYQuant Data Lifecycle Manager.

Manages the complete data lifecycle from hot storage to cold archive:
    Hot Storage → Warm Storage → Cold Archive → Deletion

Supports:
    - Tier-based lifecycle policies
    - Automatic tier transitions
    - Data compression before archiving
    - Retention enforcement
    - Cost optimization

Usage::

    lm = LifecycleManager(LifecycleConfig(), lakehouse)
    lm.add_policy("tick_lifecycle", "market_tick", hot_days=30, warm_days=60, cold_days=90)
    lm.apply_policies()
    stats = lm.get_cost_estimate()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from services.data_platform.config import (
    LifecycleConfig,
    LifecycleAction,
    StorageTier,
)
from services.data_platform.lakehouse import DataLakehouse, DataFile


# ============================================================================
# Lifecycle Types
# ============================================================================


@dataclass
class LifecyclePolicy:
    """A data lifecycle policy defining tier transitions."""

    name: str
    dataset: str
    hot_retention_days: int = 30
    warm_retention_days: int = 60
    cold_retention_days: int = 365
    archive_format: str = "parquet"  # parquet, avro, orc
    compress: bool = True
    compression_codec: str = "snappy"
    enabled: bool = True
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_applied: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "dataset": self.dataset,
            "hot_retention_days": self.hot_retention_days,
            "warm_retention_days": self.warm_retention_days,
            "cold_retention_days": self.cold_retention_days,
            "archive_format": self.archive_format,
            "compress": self.compress,
            "compression_codec": self.compression_codec,
            "enabled": self.enabled,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "last_applied": self.last_applied.isoformat() if self.last_applied else None,
            "metadata": self.metadata,
        }


@dataclass
class TierTransition:
    """Record of a data tier transition."""

    dataset: str
    file_id: str
    from_tier: StorageTier
    to_tier: StorageTier
    transitioned_at: datetime = field(default_factory=datetime.utcnow)
    reason: str = ""
    size_bytes: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LifecycleReport:
    """Report from a lifecycle policy application."""

    policy_name: str
    dataset: str
    applied_at: datetime = field(default_factory=datetime.utcnow)
    transitions: List[TierTransition] = field(default_factory=list)
    files_hot_to_warm: int = 0
    files_warm_to_cold: int = 0
    files_deleted: int = 0
    size_freed_bytes: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_name": self.policy_name,
            "dataset": self.dataset,
            "applied_at": self.applied_at.isoformat(),
            "files_hot_to_warm": self.files_hot_to_warm,
            "files_warm_to_cold": self.files_warm_to_cold,
            "files_deleted": self.files_deleted,
            "size_freed_bytes": self.size_freed_bytes,
            "errors": self.errors,
        }


@dataclass
class CostEstimate:
    """Estimated storage cost breakdown."""

    dataset: str
    hot_cost_monthly: float = 0.0
    warm_cost_monthly: float = 0.0
    cold_cost_monthly: float = 0.0
    total_cost_monthly: float = 0.0
    hot_size_gb: float = 0.0
    warm_size_gb: float = 0.0
    cold_size_gb: float = 0.0
    estimated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "hot_cost_monthly": round(self.hot_cost_monthly, 2),
            "warm_cost_monthly": round(self.warm_cost_monthly, 2),
            "cold_cost_monthly": round(self.cold_cost_monthly, 2),
            "total_cost_monthly": round(self.total_cost_monthly, 2),
            "hot_size_gb": round(self.hot_size_gb, 2),
            "warm_size_gb": round(self.warm_size_gb, 2),
            "cold_size_gb": round(self.cold_size_gb, 2),
            "estimated_at": self.estimated_at.isoformat(),
        }


# ============================================================================
# Lifecycle Manager
# ============================================================================


class LifecycleManager:
    """Data Lifecycle Manager.

    Manages the complete data lifecycle with automated tier transitions
    and retention enforcement.

    Cost model (configurable per GB/month):
        - Hot:  $0.023/GB  (SSD)
        - Warm: $0.0125/GB (HDD)
        - Cold: $0.004/GB  (Archive)

    Usage::

        lm = LifecycleManager(LifecycleConfig(), lakehouse)
        lm.add_policy("standard", "market_tick", hot_days=30, warm_days=90)
        report = lm.apply_policy("standard")
    """

    # Cost per GB per month by tier (configurable)
    COST_PER_GB = {
        StorageTier.HOT: 0.023,
        StorageTier.WARM: 0.0125,
        StorageTier.COLD: 0.004,
    }

    def __init__(
        self,
        config: Optional[LifecycleConfig] = None,
        lakehouse: Optional[DataLakehouse] = None,
    ) -> None:
        self.config = config or LifecycleConfig()
        self.lakehouse = lakehouse
        self._policies: Dict[str, LifecyclePolicy] = {}
        self._transition_history: List[TierTransition] = []

    # ------------------------------------------------------------------
    # Policy Management
    # ------------------------------------------------------------------

    def add_policy(
        self,
        name: str,
        dataset: str,
        hot_retention_days: Optional[int] = None,
        warm_retention_days: Optional[int] = None,
        cold_retention_days: Optional[int] = None,
        **kwargs: Any,
    ) -> LifecyclePolicy:
        """Add a lifecycle policy for a dataset.

        Args:
            name: Policy name.
            dataset: Dataset name.
            hot_retention_days: Days in hot tier (default from config).
            warm_retention_days: Days in warm tier.
            cold_retention_days: Days in cold tier before deletion.
            **kwargs: Additional policy settings.

        Returns:
            LifecyclePolicy.
        """
        policy = LifecyclePolicy(
            name=name,
            dataset=dataset,
            hot_retention_days=hot_retention_days or self.config.hot_retention_days,
            warm_retention_days=warm_retention_days or self.config.warm_retention_days,
            cold_retention_days=cold_retention_days or self.config.cold_retention_days,
            description=kwargs.pop("description", ""),
            metadata=kwargs,
        )
        self._policies[name] = policy
        return policy

    def get_policy(self, name: str) -> Optional[LifecyclePolicy]:
        """Get a lifecycle policy by name."""
        return self._policies.get(name)

    def get_policy_for_dataset(self, dataset: str) -> Optional[LifecyclePolicy]:
        """Get the policy applicable to a dataset."""
        for policy in self._policies.values():
            if policy.dataset == dataset:
                return policy
        return None

    def list_policies(self) -> List[LifecyclePolicy]:
        """List all lifecycle policies."""
        return list(self._policies.values())

    # ------------------------------------------------------------------
    # Policy Application
    # ------------------------------------------------------------------

    def apply_policy(self, policy_name: str) -> LifecycleReport:
        """Apply a lifecycle policy to its dataset.

        Transitions data between tiers based on age.

        Args:
            policy_name: Policy name.

        Returns:
            LifecycleReport with transition details.
        """
        policy = self._policies.get(policy_name)
        if not policy:
            return LifecycleReport(
                policy_name=policy_name,
                dataset="",
                errors=[f"Policy '{policy_name}' not found"],
            )

        if not policy.enabled:
            return LifecycleReport(
                policy_name=policy_name,
                dataset=policy.dataset,
                errors=["Policy is disabled"],
            )

        report = LifecycleReport(
            policy_name=policy_name,
            dataset=policy.dataset,
        )

        now = datetime.utcnow()
        hot_cutoff = now - timedelta(days=policy.hot_retention_days)
        warm_cutoff = now - timedelta(days=policy.hot_retention_days + policy.warm_retention_days)
        delete_cutoff = now - timedelta(
            days=policy.hot_retention_days + policy.warm_retention_days + policy.cold_retention_days
        )

        if not self.lakehouse:
            return report

        # Process files
        for file_id, df in list(self.lakehouse._files.items()):
            if df.dataset != policy.dataset:
                continue

            age = now - df.created_at

            # Check for deletion
            if age > timedelta(days=policy.hot_retention_days + policy.warm_retention_days + policy.cold_retention_days):
                transition = TierTransition(
                    dataset=policy.dataset,
                    file_id=file_id,
                    from_tier=df.tier,
                    to_tier=StorageTier.COLD,  # Mark as expired
                    reason="Retention period expired",
                    size_bytes=df.size_bytes,
                )
                report.transitions.append(transition)
                report.files_deleted += 1
                report.size_freed_bytes += df.size_bytes

                # Remove file
                del self.lakehouse._files[file_id]

            # Hot → Warm
            elif df.tier == StorageTier.HOT and age > timedelta(days=policy.hot_retention_days):
                df.tier = StorageTier.WARM
                transition = TierTransition(
                    dataset=policy.dataset,
                    file_id=file_id,
                    from_tier=StorageTier.HOT,
                    to_tier=StorageTier.WARM,
                    reason=f"Exceeded hot retention ({policy.hot_retention_days}d)",
                    size_bytes=df.size_bytes,
                )
                report.transitions.append(transition)
                report.files_hot_to_warm += 1

            # Warm → Cold
            elif df.tier == StorageTier.WARM and age > timedelta(days=policy.hot_retention_days + policy.warm_retention_days):
                df.tier = StorageTier.COLD
                transition = TierTransition(
                    dataset=policy.dataset,
                    file_id=file_id,
                    from_tier=StorageTier.WARM,
                    to_tier=StorageTier.COLD,
                    reason=f"Exceeded warm retention ({policy.warm_retention_days}d)",
                    size_bytes=df.size_bytes,
                )
                report.transitions.append(transition)
                report.files_warm_to_cold += 1

        policy.last_applied = now
        self._transition_history.extend(report.transitions)
        return report

    def apply_all_policies(self) -> List[LifecycleReport]:
        """Apply all enabled lifecycle policies.

        Returns:
            List of LifecycleReport for each policy.
        """
        reports: List[LifecycleReport] = []
        for policy_name in self._policies:
            policy = self._policies[policy_name]
            if policy.enabled:
                reports.append(self.apply_policy(policy_name))
        return reports

    # ------------------------------------------------------------------
    # Cost Estimation
    # ------------------------------------------------------------------

    def estimate_cost(self, dataset: str) -> CostEstimate:
        """Estimate monthly storage cost for a dataset.

        Args:
            dataset: Dataset name.

        Returns:
            CostEstimate.
        """
        estimate = CostEstimate(dataset=dataset)

        if not self.lakehouse:
            return estimate

        for df in self.lakehouse._files.values():
            if df.dataset != dataset:
                continue

            size_gb = df.size_bytes / (1024 ** 3)

            if df.tier == StorageTier.HOT:
                estimate.hot_size_gb += size_gb
            elif df.tier == StorageTier.WARM:
                estimate.warm_size_gb += size_gb
            elif df.tier == StorageTier.COLD:
                estimate.cold_size_gb += size_gb

        estimate.hot_cost_monthly = estimate.hot_size_gb * self.COST_PER_GB[StorageTier.HOT]
        estimate.warm_cost_monthly = estimate.warm_size_gb * self.COST_PER_GB[StorageTier.WARM]
        estimate.cold_cost_monthly = estimate.cold_size_gb * self.COST_PER_GB[StorageTier.COLD]
        estimate.total_cost_monthly = (
            estimate.hot_cost_monthly + estimate.warm_cost_monthly + estimate.cold_cost_monthly
        )

        return estimate

    def estimate_all_costs(self) -> List[CostEstimate]:
        """Estimate costs for all datasets with policies.

        Returns:
            List of CostEstimate.
        """
        estimates: List[CostEstimate] = []
        datasets_seen: set = set()

        for policy in self._policies.values():
            if policy.dataset not in datasets_seen:
                datasets_seen.add(policy.dataset)
                estimates.append(self.estimate_cost(policy.dataset))

        return estimates

    # ------------------------------------------------------------------
    # History & Stats
    # ------------------------------------------------------------------

    def get_transition_history(
        self, dataset: Optional[str] = None, limit: int = 100
    ) -> List[TierTransition]:
        """Get tier transition history.

        Args:
            dataset: Filter by dataset.
            limit: Maximum entries.

        Returns:
            List of TierTransition.
        """
        history = list(self._transition_history)
        if dataset:
            history = [t for t in history if t.dataset == dataset]
        return sorted(history, key=lambda t: t.transitioned_at, reverse=True)[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get lifecycle management statistics."""
        total_transitions = len(self._transition_history)
        total_deleted = sum(
            1 for t in self._transition_history
            if "expired" in t.reason.lower()
        )
        total_freed_bytes = sum(
            t.size_bytes for t in self._transition_history
            if "expired" in t.reason.lower()
        )

        return {
            "total_policies": len(self._policies),
            "enabled_policies": sum(1 for p in self._policies.values() if p.enabled),
            "total_transitions": total_transitions,
            "files_deleted": total_deleted,
            "total_freed_gb": round(total_freed_bytes / (1024 ** 3), 2),
            "by_transition_type": {
                "hot_to_warm": sum(1 for t in self._transition_history if t.to_tier == StorageTier.WARM),
                "warm_to_cold": sum(1 for t in self._transition_history if t.to_tier == StorageTier.COLD),
                "deleted": total_deleted,
            },
        }
