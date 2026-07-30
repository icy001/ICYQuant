"""ICYQuant Data Governance.

Unified data governance framework supporting:
    - Data Ownership assignment
    - Data Classification (public/internal/confidential/restricted)
    - Retention policy enforcement
    - Audit logging
    - Policy compliance checking

Usage::

    gov = GovernanceEngine(GovernanceConfig())
    gov.assign_owner("market_tick", "market_team")
    gov.classify("market_tick", DataClassification.INTERNAL)
    violations = gov.check_compliance("market_tick")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from services.data_platform.config import (
    GovernanceConfig,
    DataClassification,
)


# ============================================================================
# Governance Types
# ============================================================================


@dataclass
class DataOwner:
    """Data ownership information."""

    dataset: str
    owner: str
    team: str = ""
    contact: str = ""
    assigned_at: datetime = field(default_factory=datetime.utcnow)
    backup_owner: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "owner": self.owner,
            "team": self.team,
            "contact": self.contact,
            "assigned_at": self.assigned_at.isoformat(),
            "backup_owner": self.backup_owner,
            "metadata": self.metadata,
        }


@dataclass
class RetentionPolicy:
    """Data retention policy."""

    name: str
    dataset: str
    retention_days: int
    archive_after_days: int = 0
    delete_after_days: int = 0
    applies_to: List[str] = field(default_factory=list)  # Wildcard patterns
    description: str = ""
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "dataset": self.dataset,
            "retention_days": self.retention_days,
            "archive_after_days": self.archive_after_days,
            "delete_after_days": self.delete_after_days,
            "applies_to": self.applies_to,
            "description": self.description,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }


@dataclass
class AuditEntry:
    """A single audit log entry."""

    entry_id: str
    dataset: str
    action: str  # read, write, delete, schema_change, etc.
    actor: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "dataset": self.dataset,
            "action": self.action,
            "actor": self.actor,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "success": self.success,
            "error_message": self.error_message,
        }


@dataclass
class ComplianceReport:
    """Report on governance compliance."""

    dataset: str
    is_compliant: bool = True
    violations: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    owner_assigned: bool = False
    classification_set: bool = False
    retention_set: bool = False
    checked_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "is_compliant": self.is_compliant,
            "violations": self.violations,
            "warnings": self.warnings,
            "owner_assigned": self.owner_assigned,
            "classification_set": self.classification_set,
            "retention_set": self.retention_set,
            "checked_at": self.checked_at.isoformat(),
        }


# ============================================================================
# Governance Engine
# ============================================================================


class GovernanceEngine:
    """Data Governance Engine.

    Manages data ownership, classification, retention policies,
    and audit logging for all data assets.

    Usage::

        gov = GovernanceEngine(GovernanceConfig())
        gov.assign_owner("market_tick", "alice", team="Market Data")
        gov.set_classification("market_tick", DataClassification.INTERNAL)
        gov.add_retention_policy("tick_retention", "market_tick", retention_days=90)
        gov.log_audit("market_tick", "read", "bob")
    """

    def __init__(self, config: Optional[GovernanceConfig] = None) -> None:
        self.config = config or GovernanceConfig()
        self._owners: Dict[str, DataOwner] = {}
        self._classifications: Dict[str, DataClassification] = {}
        self._retention_policies: Dict[str, RetentionPolicy] = {}
        self._audit_log: List[AuditEntry] = []
        self._audit_counter: int = 0

    # ------------------------------------------------------------------
    # Ownership
    # ------------------------------------------------------------------

    def assign_owner(
        self,
        dataset: str,
        owner: str,
        team: str = "",
        contact: str = "",
        backup_owner: str = "",
    ) -> DataOwner:
        """Assign an owner to a dataset.

        Args:
            dataset: Dataset name.
            owner: Owner identifier.
            team: Team name.
            contact: Contact information.
            backup_owner: Backup owner identifier.

        Returns:
            DataOwner record.
        """
        data_owner = DataOwner(
            dataset=dataset,
            owner=owner,
            team=team,
            contact=contact,
            backup_owner=backup_owner,
        )
        self._owners[dataset] = data_owner
        return data_owner

    def get_owner(self, dataset: str) -> Optional[DataOwner]:
        """Get the owner of a dataset."""
        return self._owners.get(dataset)

    def list_owners(self) -> Dict[str, DataOwner]:
        """List all dataset owners."""
        return dict(self._owners)

    def find_datasets_by_owner(self, owner: str) -> List[str]:
        """Find all datasets owned by a specific person/team.

        Args:
            owner: Owner identifier.

        Returns:
            List of dataset names.
        """
        return [
            ds for ds, o in self._owners.items()
            if o.owner == owner or o.backup_owner == owner
        ]

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def set_classification(
        self, dataset: str, classification: DataClassification
    ) -> None:
        """Set the data classification for a dataset.

        Args:
            dataset: Dataset name.
            classification: Data classification level.
        """
        self._classifications[dataset] = classification

    def get_classification(self, dataset: str) -> Optional[DataClassification]:
        """Get the classification of a dataset."""
        return self._classifications.get(dataset)

    def list_by_classification(
        self, classification: DataClassification
    ) -> List[str]:
        """List all datasets with a specific classification.

        Args:
            classification: Data classification level.

        Returns:
            List of dataset names.
        """
        return [
            ds for ds, cls in self._classifications.items()
            if cls == classification
        ]

    # ------------------------------------------------------------------
    # Retention Policies
    # ------------------------------------------------------------------

    def add_retention_policy(
        self,
        name: str,
        dataset: str,
        retention_days: int,
        archive_after_days: int = 0,
        delete_after_days: int = 0,
        **kwargs: Any,
    ) -> RetentionPolicy:
        """Add a retention policy for a dataset.

        Args:
            name: Policy name.
            dataset: Dataset name (or wildcard pattern).
            retention_days: Days to retain data.
            archive_after_days: Days after which to archive.
            delete_after_days: Days after which to delete.
            **kwargs: Additional metadata.

        Returns:
            RetentionPolicy.
        """
        policy = RetentionPolicy(
            name=name,
            dataset=dataset,
            retention_days=retention_days,
            archive_after_days=archive_after_days,
            delete_after_days=delete_after_days,
            description=kwargs.pop("description", ""),
            metadata=kwargs,
        )
        self._retention_policies[name] = policy
        return policy

    def get_retention_policy(self, dataset: str) -> Optional[RetentionPolicy]:
        """Get the applicable retention policy for a dataset.

        Args:
            dataset: Dataset name.

        Returns:
            RetentionPolicy or None.
        """
        # Exact match first
        for policy in self._retention_policies.values():
            if policy.dataset == dataset:
                return policy

        # Pattern match
        import fnmatch
        for policy in self._retention_policies.values():
            for pattern in policy.applies_to:
                if fnmatch.fnmatch(dataset, pattern):
                    return policy

        return None

    def list_retention_policies(self) -> List[RetentionPolicy]:
        """List all retention policies."""
        return list(self._retention_policies.values())

    def get_datasets_near_expiry(self, days_threshold: int = 7) -> List[Dict[str, Any]]:
        """Get datasets approaching retention expiry.

        Args:
            days_threshold: Days threshold for near-expiry.

        Returns:
            List of datasets near expiry with days remaining.
        """
        near_expiry: List[Dict[str, Any]] = []
        now = datetime.utcnow()

        for policy in self._retention_policies.values():
            if not policy.enabled:
                continue
            # In production, would check actual data age
            # Here return policy info
            near_expiry.append({
                "dataset": policy.dataset,
                "policy": policy.name,
                "retention_days": policy.retention_days,
                "archive_after_days": policy.archive_after_days,
                "delete_after_days": policy.delete_after_days,
            })

        return near_expiry

    # ------------------------------------------------------------------
    # Audit Logging
    # ------------------------------------------------------------------

    def log_audit(
        self,
        dataset: str,
        action: str,
        actor: str,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        error_message: str = "",
    ) -> AuditEntry:
        """Log an audit entry.

        Args:
            dataset: Dataset name.
            action: Action performed (read, write, delete, etc.).
            actor: Who performed the action.
            success: Whether the action succeeded.
            details: Additional details.
            error_message: Error message if failed.

        Returns:
            AuditEntry.
        """
        self._audit_counter += 1
        entry = AuditEntry(
            entry_id=f"audit_{self._audit_counter}",
            dataset=dataset,
            action=action,
            actor=actor,
            success=success,
            details=details or {},
            error_message=error_message,
        )

        self._audit_log.append(entry)

        # Trim old entries
        if len(self._audit_log) > self.config.audit_retention_days * 1000:
            self._audit_log = self._audit_log[-self.config.audit_retention_days * 1000:]

        return entry

    def get_audit_log(
        self,
        dataset: Optional[str] = None,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """Query the audit log.

        Args:
            dataset: Filter by dataset.
            actor: Filter by actor.
            action: Filter by action.
            since: Filter by timestamp.
            limit: Maximum entries to return.

        Returns:
            List of matching AuditEntry objects.
        """
        results = list(self._audit_log)

        if dataset:
            results = [e for e in results if e.dataset == dataset]
        if actor:
            results = [e for e in results if e.actor == actor]
        if action:
            results = [e for e in results if e.action == action]
        if since:
            results = [e for e in results if e.timestamp >= since]

        # Most recent first
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[:limit]

    def get_audit_stats(self) -> Dict[str, Any]:
        """Get audit log statistics."""
        actions: Dict[str, int] = {}
        actors: Dict[str, int] = {}
        datasets: Dict[str, int] = {}

        for entry in self._audit_log:
            actions[entry.action] = actions.get(entry.action, 0) + 1
            actors[entry.actor] = actors.get(entry.actor, 0) + 1
            datasets[entry.dataset] = datasets.get(entry.dataset, 0) + 1

        return {
            "total_entries": len(self._audit_log),
            "by_action": actions,
            "by_actor": actors,
            "by_dataset": datasets,
            "failed_actions": sum(1 for e in self._audit_log if not e.success),
        }

    # ------------------------------------------------------------------
    # Compliance
    # ------------------------------------------------------------------

    def check_compliance(self, dataset: str) -> ComplianceReport:
        """Check governance compliance for a dataset.

        Verifies that:
        - Owner is assigned (if required)
        - Classification is set (if required)
        - Retention policy exists

        Args:
            dataset: Dataset name.

        Returns:
            ComplianceReport.
        """
        report = ComplianceReport(dataset=dataset)

        # Check ownership
        if self.config.require_owner:
            owner = self._owners.get(dataset)
            if not owner:
                report.violations.append({
                    "type": "missing_owner",
                    "message": f"No owner assigned for dataset '{dataset}'",
                    "severity": "high",
                })
                report.is_compliant = False
            else:
                report.owner_assigned = True

        # Check classification
        if self.config.require_classification:
            classification = self._classifications.get(dataset)
            if not classification:
                report.violations.append({
                    "type": "missing_classification",
                    "message": f"No classification set for dataset '{dataset}'",
                    "severity": "medium",
                })
                report.is_compliant = False
            else:
                report.classification_set = True

        # Check retention
        policy = self.get_retention_policy(dataset)
        if policy:
            report.retention_set = True
        else:
            report.warnings.append({
                "type": "no_retention_policy",
                "message": f"No retention policy for dataset '{dataset}'",
                "severity": "low",
            })

        return report

    def check_all_compliance(self) -> List[ComplianceReport]:
        """Check compliance for all datasets with owners or classifications."""
        all_datasets = set(self._owners.keys()) | set(self._classifications.keys())
        return [self.check_compliance(ds) for ds in all_datasets]

    def get_compliance_summary(self) -> Dict[str, Any]:
        """Get a summary of governance compliance across all datasets."""
        reports = self.check_all_compliance()

        compliant = sum(1 for r in reports if r.is_compliant)
        total = len(reports)

        return {
            "total_datasets": total,
            "compliant": compliant,
            "non_compliant": total - compliant,
            "compliance_rate": round(compliant / total * 100, 2) if total > 0 else 100.0,
            "total_violations": sum(len(r.violations) for r in reports),
            "total_warnings": sum(len(r.warnings) for r in reports),
            "violations": [
                v for r in reports for v in r.violations
            ],
        }
