"""
ICYQuant Data Governance Center.

Commit 16 Part 1.5 — Central governance engine for the unified data platform.
Manages data ownership, classification, compliance, retention policies,
and governance workflows across all datasets.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GovernanceStatus(str, Enum):
    """Governance compliance status."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    AT_RISK = "at_risk"
    EXEMPTED = "exempted"
    UNKNOWN = "unknown"


class DataClassification(str, Enum):
    """Data sensitivity classification."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass
class DataOwner:
    """Data ownership information."""
    owner_id: str = ""
    name: str = ""
    team: str = ""
    email: str = ""
    is_primary: bool = True


@dataclass
class RetentionPolicy:
    """Data retention policy."""
    policy_id: str = ""
    dataset_id: str = ""
    retention_days: int = 365
    archive_days: int = 730
    delete_after_archive: bool = True
    min_versions: int = 1
    max_versions: int = 100
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComplianceReport:
    """Governance compliance report for a dataset."""
    dataset_id: str = ""
    status: GovernanceStatus = GovernanceStatus.UNKNOWN
    classification: DataClassification = DataClassification.INTERNAL
    has_owner: bool = False
    has_retention_policy: bool = False
    has_quality_checks: bool = False
    has_lineage: bool = False
    has_access_control: bool = False
    issues: list[str] = field(default_factory=list)
    last_checked: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEntry:
    """An audit log entry."""
    entry_id: str = ""
    principal: str = ""
    operation: str = ""
    dataset_id: str = ""
    timestamp: Optional[datetime] = None
    success: bool = True
    details: dict[str, Any] = field(default_factory=dict)


class DataGovernance:
    """Central data governance engine.

    Provides:
      - Data ownership management
      - Classification and sensitivity labeling
      - Retention policy enforcement
      - Compliance checking and reporting
      - Governance workflow automation
    """

    def __init__(
        self,
        catalog: Any = None,
        metadata: Any = None,
        schema: Any = None,
    ) -> None:
        self._catalog = catalog
        self._metadata = metadata
        self._schema = schema
        self._owners: dict[str, list[DataOwner]] = {}
        self._policies: dict[str, RetentionPolicy] = {}
        self._audit_log: list[AuditEntry] = []
        self._audit_counter = 0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Ownership
    # ------------------------------------------------------------------

    async def assign_owner(self, dataset_id: str, owner: DataOwner) -> None:
        """Assign a data owner to a dataset."""
        async with self._lock:
            if dataset_id not in self._owners:
                self._owners[dataset_id] = []
            # Replace existing primary if this is primary
            if owner.is_primary:
                self._owners[dataset_id] = [o for o in self._owners[dataset_id] if not o.is_primary]
            self._owners[dataset_id].append(owner)
        logger.info("Owner assigned to %s: %s", dataset_id, owner.name)

    async def get_owners(self, dataset_id: str) -> list[DataOwner]:
        """Get all owners for a dataset."""
        return self._owners.get(dataset_id, [])

    async def get_primary_owner(self, dataset_id: str) -> Optional[DataOwner]:
        """Get the primary owner for a dataset."""
        owners = self._owners.get(dataset_id, [])
        for owner in owners:
            if owner.is_primary:
                return owner
        return owners[0] if owners else None

    # ------------------------------------------------------------------
    # Retention Policy
    # ------------------------------------------------------------------

    async def set_retention_policy(self, policy: RetentionPolicy) -> str:
        """Set a retention policy for a dataset."""
        async with self._lock:
            policy.updated_at = datetime.now(timezone.utc)
            if not policy.created_at:
                policy.created_at = policy.updated_at
            self._policies[policy.policy_id] = policy
        logger.info("Retention policy set: %s (dataset=%s, days=%d)",
                    policy.policy_id, policy.dataset_id, policy.retention_days)
        return policy.policy_id

    async def get_retention_policy(self, policy_id: str) -> Optional[RetentionPolicy]:
        """Get a retention policy by ID."""
        return self._policies.get(policy_id)

    async def get_dataset_retention(self, dataset_id: str) -> Optional[RetentionPolicy]:
        """Get the retention policy for a dataset."""
        for policy in self._policies.values():
            if policy.dataset_id == dataset_id:
                return policy
        return None

    # ------------------------------------------------------------------
    # Compliance
    # ------------------------------------------------------------------

    async def check_compliance(self, dataset_id: str) -> ComplianceReport:
        """Check governance compliance for a dataset."""
        report = ComplianceReport(
            dataset_id=dataset_id,
            last_checked=datetime.now(timezone.utc),
        )

        # Check ownership
        owners = await self.get_owners(dataset_id)
        report.has_owner = len(owners) > 0
        if not report.has_owner:
            report.issues.append("No data owner assigned")

        # Check retention policy
        report.has_retention_policy = await self.get_dataset_retention(dataset_id) is not None
        if not report.has_retention_policy:
            report.issues.append("No retention policy configured")

        # Determine status
        if not report.issues:
            report.status = GovernanceStatus.COMPLIANT
        elif len(report.issues) <= 1:
            report.status = GovernanceStatus.AT_RISK
        else:
            report.status = GovernanceStatus.NON_COMPLIANT

        return report

    async def check_all_compliance(self) -> dict[str, ComplianceReport]:
        """Check compliance for all datasets in the catalog."""
        reports = {}
        if self._catalog:
            entries = await self._catalog.list_all()
            for entry in entries:
                reports[entry.dataset_id] = await self.check_compliance(entry.dataset_id)
        return reports

    # ------------------------------------------------------------------
    # Audit Logging
    # ------------------------------------------------------------------

    async def log_audit(self, entry: AuditEntry) -> None:
        """Record an audit entry."""
        async with self._lock:
            self._audit_counter += 1
            entry.entry_id = f"audit-{self._audit_counter:08d}"
            entry.timestamp = datetime.now(timezone.utc)
            self._audit_log.append(entry)

    async def get_audit_log(
        self, dataset_id: Optional[str] = None, principal: Optional[str] = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Query the audit log with filters."""
        results = self._audit_log
        if dataset_id:
            results = [e for e in results if e.dataset_id == dataset_id]
        if principal:
            results = [e for e in results if e.principal == principal]
        return results[-limit:]

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def managed_dataset_count(self) -> int:
        return len(self._owners)

    @property
    def policy_count(self) -> int:
        return len(self._policies)

    @property
    def audit_count(self) -> int:
        return len(self._audit_log)
