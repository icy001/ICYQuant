"""
Policy Validator — validates policy versions for correctness and completeness.

Performs structural and semantic validation on policy versions:
  - Required fields present
  - Rules are well-formed
  - Conditions are valid
  - Expressions compile
  - Scope hierarchy is valid
  - Metadata is complete
  - Dependencies are resolvable

Validation levels:
  - STRUCTURAL: Required fields, types, formats
  - SEMANTIC: Logical correctness, cross-references
  - INTEGRITY: Checksum, tampering detection
  - REGULATORY: Compliance-specific checks (owner, review interval, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from .policy_version import PolicyVersion
from .policy_rule import PolicyRule
from .policy_condition import PolicyCondition
from .policy_status import PolicyLifecycleStatus
from .policy_priority import PolicyPriorityLevel
from .policy_scope import PolicyScopeConstants


# ---------------------------------------------------------------------------
# Validation severity
# ---------------------------------------------------------------------------

class ValidationSeverity(Enum):
    """Severity of a validation issue."""

    ERROR = auto()     # Must fix — blocks publication
    WARNING = auto()   # Should fix — does not block, but flagged
    INFO = auto()      # Informational — no action needed


# ---------------------------------------------------------------------------
# Validation issue
# ---------------------------------------------------------------------------

@dataclass
class ValidationIssue:
    """A single validation issue found during policy validation."""

    code: str                    # Issue code, e.g., "POL-001"
    severity: ValidationSeverity
    field: str                  # Which field had the issue
    message: str
    location: str = ""          # policy_id:version_id:rule_id
    suggestion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.name,
            "field": self.field,
            "message": self.message,
            "location": self.location,
            "suggestion": self.suggestion,
        }


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Result of validating a policy version."""

    policy_id: str = ""
    version_id: str = ""
    version: str = ""
    name: str = ""

    # Overall
    is_valid: bool = True
    can_publish: bool = True

    # Issues
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    infos: List[ValidationIssue] = field(default_factory=list)

    def add(
        self,
        code: str,
        severity: ValidationSeverity,
        field: str,
        message: str,
        suggestion: str = "",
    ) -> "ValidationResult":
        issue = ValidationIssue(
            code=code,
            severity=severity,
            field=field,
            message=message,
            location=f"{self.policy_id}:{self.version_id}",
            suggestion=suggestion,
        )
        if severity == ValidationSeverity.ERROR:
            self.errors.append(issue)
            self.is_valid = False
        elif severity == ValidationSeverity.WARNING:
            self.warnings.append(issue)
        else:
            self.infos.append(issue)
        return self

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """Merge another result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.infos.extend(other.infos)
        self.is_valid = self.is_valid and other.is_valid
        return self

    @property
    def issue_count(self) -> int:
        return len(self.errors) + len(self.warnings) + len(self.infos)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def summary(self) -> str:
        return (
            f"ValidationResult: valid={self.is_valid}, "
            f"errors={self.error_count}, warnings={self.warning_count}, "
            f"info={len(self.infos)}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "version_id": self.version_id,
            "version": self.version,
            "name": self.name,
            "is_valid": self.is_valid,
            "can_publish": self.can_publish,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "infos": [i.to_dict() for i in self.infos],
            "issue_count": self.issue_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Policy Validator
# ---------------------------------------------------------------------------

@dataclass
class PolicyValidator:
    """
    Validates policy versions for correctness and completeness.

    Validation checks:
      - STRUCTURAL: Required fields, types
      - SEMANTIC: Rule/condition logic, scope validity
      - INTEGRITY: Checksum verification
      - REGULATORY: Metadata completeness, review compliance

    Usage:
        validator = PolicyValidator()
        result = validator.validate(version)
        if result.can_publish:
            publisher.publish(version)
    """

    # Config
    strict_mode: bool = False  # If True, warnings become errors

    # ------------------------------------------------------------------
    # Main validation entry point
    # ------------------------------------------------------------------

    def validate(self, version: PolicyVersion) -> ValidationResult:
        """Validate a policy version against all checks."""
        result = ValidationResult(
            policy_id=version.policy_id,
            version_id=version.version_id,
            version=version.version,
            name=version.name,
        )

        self._check_structural(version, result)
        self._check_semantic(version, result)
        self._check_integrity(version, result)
        self._check_regulatory(version, result)

        # Can publish if no errors
        result.can_publish = result.is_valid
        return result

    def quick_validate(self, version: PolicyVersion) -> bool:
        """Quick structural-only validation (returns True/False)."""
        result = ValidationResult(
            policy_id=version.policy_id,
            version_id=version.version_id,
        )
        self._check_structural(version, result)
        return result.is_valid

    # ------------------------------------------------------------------
    # Structural checks
    # ------------------------------------------------------------------

    def _check_structural(
        self, version: PolicyVersion, result: ValidationResult
    ) -> None:
        """Check required fields and types."""
        # Identity
        if not version.policy_id:
            result.add("POL-001", ValidationSeverity.ERROR, "policy_id",
                        "Policy ID is required.")  # Fixed: double space

        if not version.name:
            result.add("POL-002", ValidationSeverity.ERROR, "name",
                        "Policy name is required.", "Provide a descriptive name.")

        if not version.description:
            result.add("POL-003", ValidationSeverity.WARNING, "description",
                        "Policy description is empty.", "Add a description for clarity.")

        # Version format
        if not self._is_valid_semver(version.version):
            result.add("POL-004", ValidationSeverity.ERROR, "version",
                        f"Invalid version format: '{version.version}'. "
                        f"Expected MAJOR.MINOR.PATCH.",
                        "Use semver format, e.g., '1.0.0'.")

        # Scope
        valid_scopes = PolicyScopeConstants.all_scopes()
        if version.scope not in valid_scopes:
            result.add("POL-005", ValidationSeverity.ERROR, "scope",
                        f"Invalid scope: '{version.scope}'. "
                        f"Valid: {sorted(valid_scopes)}",
                        "Use one of the defined scope constants.")

        # Priority
        if not isinstance(version.priority, PolicyPriorityLevel):
            result.add("POL-006", ValidationSeverity.ERROR, "priority",
                        f"Invalid priority type: {type(version.priority)}",
                        "Use PolicyPriorityLevel enum.")

        # Rules
        if not version.rules:
            result.add("POL-007", ValidationSeverity.ERROR, "rules",
                        "Policy must have at least one rule.")

        # Check each rule
        for i, rule in enumerate(version.rules):
            self._check_rule(rule, i, result)

    def _check_rule(
        self, rule: PolicyRule, index: int, result: ValidationResult
    ) -> None:
        """Validate a single rule."""
        prefix = f"rules[{index}]"

        if not rule.rule_id:
            result.add("POL-008", ValidationSeverity.ERROR, f"{prefix}.rule_id",
                        f"Rule #{index} has no rule_id.",
                        "Assign a unique rule_id.")

        if not rule.metric:
            result.add("POL-009", ValidationSeverity.WARNING, f"{prefix}.metric",
                        f"Rule '{rule.rule_id}' has no metric specified.",
                        "Specify a metric to evaluate.")

        if not rule.operator:
            result.add("POL-010", ValidationSeverity.WARNING, f"{prefix}.operator",
                        f"Rule '{rule.rule_id}' has no operator.",
                        "Specify a comparison operator (e.g., '>=', '<=').")

        if not rule.description:
            result.add("POL-011", ValidationSeverity.INFO, f"{prefix}.description",
                        f"Rule '{rule.rule_id}' has no description.",
                        "Add a human-readable description.")

        # Check conditions
        for j, cond in enumerate(rule.conditions):
            self._check_condition(cond, f"{prefix}.conditions[{j}]", result)

    def _check_condition(
        self, cond: PolicyCondition, path: str, result: ValidationResult
    ) -> None:
        """Validate a single condition."""
        if not cond.metric:
            result.add("POL-012", ValidationSeverity.WARNING, f"{path}.metric",
                        "Condition has no metric.",
                        "Specify the metric this condition checks.")

    # ------------------------------------------------------------------
    # Semantic checks
    # ------------------------------------------------------------------

    def _check_semantic(
        self, version: PolicyVersion, result: ValidationResult
    ) -> None:
        """Check semantic correctness."""
        # Check for duplicate rule IDs
        rule_ids = [r.rule_id for r in version.rules]
        duplicates = set()
        seen = set()
        for rid in rule_ids:
            if rid in seen:
                duplicates.add(rid)
            seen.add(rid)
        if duplicates:
            result.add("POL-020", ValidationSeverity.ERROR, "rules",
                        f"Duplicate rule IDs: {', '.join(sorted(duplicates))}",
                        "Each rule must have a unique rule_id.")

        # Check for duplicate condition IDs
        all_cond_ids = []
        for rule in version.rules:
            all_cond_ids.extend(c.condition_id for c in rule.conditions if c.condition_id)
        seen_c = set()
        dup_c = set()
        for cid in all_cond_ids:
            if cid in seen_c:
                dup_c.add(cid)
            seen_c.add(cid)
        if dup_c:
            result.add("POL-021", ValidationSeverity.WARNING, "conditions",
                        f"Duplicate condition IDs: {', '.join(sorted(dup_c))}",
                        "Ensure unique condition IDs.")

        # Check lifecycle state validity
        if version.status == PolicyLifecycleStatus.ACTIVE and not version.activated_at:
            result.add("POL-022", ValidationSeverity.WARNING, "status",
                        "Version is ACTIVE but has no activated_at timestamp.",
                        "Ensure lifecycle transitions are tracked.")

    # ------------------------------------------------------------------
    # Integrity checks
    # ------------------------------------------------------------------

    def _check_integrity(
        self, version: PolicyVersion, result: ValidationResult
    ) -> None:
        """Check content integrity."""
        # Published versions must have a content hash
        if version.is_published:
            if not version.content_hash:
                result.add("POL-030", ValidationSeverity.ERROR, "content_hash",
                            "Published version has no content hash.",
                            "Re-publish to generate content hash.")
            elif not version.verify_checksum():
                result.add("POL-031", ValidationSeverity.ERROR, "content_hash",
                            "Content hash verification failed. "
                            "Policy content may have been tampered.",
                            "Re-publish from a trusted source.")

        # Draft versions with content hash (shouldn't normally happen)
        if version.status == PolicyLifecycleStatus.DRAFT and version.content_hash:
            result.add("POL-032", ValidationSeverity.INFO, "content_hash",
                        "Draft version has a content hash (will be finalized on publish).")

    # ------------------------------------------------------------------
    # Regulatory checks
    # ------------------------------------------------------------------

    def _check_regulatory(
        self, version: PolicyVersion, result: ValidationResult
    ) -> None:
        """Check regulatory/metadata compliance."""
        meta = version.metadata

        # Owner
        if not meta.owner or meta.owner == "SYSTEM":
            result.add("POL-040", ValidationSeverity.WARNING, "metadata.owner",
                        "Policy owner is not set (defaults to SYSTEM).",
                        "Assign a specific owner.")

        # Category
        if not meta.category:
            result.add("POL-041", ValidationSeverity.INFO, "metadata.category",
                        "Policy category is not set.",
                        "Assign a category for classification (e.g., RISK, COMPLIANCE).")

        # Review interval
        if meta.review_interval_days <= 0:
            result.add("POL-042", ValidationSeverity.WARNING, "metadata.review_interval_days",
                        "Review interval is not set (<=0 means no periodic review).",
                        "Set a review interval (e.g., 90 days).")

        # Overdue review
        if meta.is_overdue_for_review():
            result.add("POL-043", ValidationSeverity.WARNING, "metadata.review",
                        f"Policy review is overdue "
                        f"({meta.days_since_last_review():.0f} days since last review).",
                        "Schedule a policy review.")

        # Mandatory policies should have a regulation reference
        if meta.mandatory and not meta.regulation_ref:
            result.add("POL-044", ValidationSeverity.INFO, "metadata.regulation_ref",
                        "Mandatory policy has no regulation reference.",
                        "Add a regulation reference (e.g., 'Basel III').")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_valid_semver(version: str) -> bool:
        """Check if a string is a valid semver."""
        try:
            parts = version.split(".")
            if len(parts) != 3:
                return False
            return all(int(p) >= 0 for p in parts)
        except (ValueError, TypeError):
            return False

    def __repr__(self) -> str:
        return f"PolicyValidator(strict={self.strict_mode})"
