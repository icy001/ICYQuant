"""
Policy Exception — structured exceptions for policy evaluation failures.

Policy exceptions are first-class domain events that capture:
  - Why a policy evaluation failed (technical, not business rule failure)
  - Which policy/version/rule was being evaluated
  - The context at the time of failure
  - Recovery guidance

Exceptions follow the Fail-Closed principle: when evaluation fails,
the decision is BLOCKED by default unless explicitly allowed.
"""

from __future__ import annotations

import traceback
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Exception categories
# ---------------------------------------------------------------------------

class PolicyExceptionCategory(Enum):
    """Categories of policy evaluation exceptions."""

    # Technical failures
    EVALUATION_ERROR = auto()     # Generic evaluation error
    METRIC_UNAVAILABLE = auto()   # Required metric not found
    CONTEXT_INVALID = auto()      # Context data is malformed
    EXPRESSION_ERROR = auto()     # Expression evaluation failed
    RULE_LOOP_DETECTED = auto()   # Circular dependency in rules

    # Lifecycle violations
    VERSION_INVALID = auto()      # Version not in a valid state
    TRANSITION_FAILED = auto()    # Lifecycle transition failed
    VERSION_CONFLICT = auto()     # Conflicting active versions
    IMMUTABLE_VIOLATION = auto()  # Attempt to modify immutable version

    # Dependency failures
    DEPENDENCY_MISSING = auto()   # Required dependency not found
    DEPENDENCY_CYCLE = auto()     # Circular dependency detected
    DEPENDENCY_VERSION_MISMATCH = auto()  # Dependency version mismatch

    # Integrity failures
    CHECKSUM_MISMATCH = auto()    # Content hash verification failed
    TAMPER_DETECTED = auto()      # Policy content tampered
    SIGNATURE_INVALID = auto()    # Digital signature invalid

    # Infrastructure
    STORAGE_ERROR = auto()        # Repository read/write failure
    CACHE_ERROR = auto()          # Cache operation failure
    LOAD_ERROR = auto()           # Policy load failure
    PUBLISH_ERROR = auto()        # Publish operation failure

    # Authorization
    UNAUTHORIZED = auto()         # Insufficient permissions
    OVERRIDE_DENIED = auto()      # Override not allowed

    # Generic
    UNKNOWN = auto()              # Unknown/unclassified error


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------

class PolicyException(Exception):
    """
    Base exception for all policy evaluation failures.

    Attributes:
        category: Classification of the failure.
        policy_id: Which policy was being evaluated.
        version_id: Which version was being evaluated.
        rule_id: Which rule was being evaluated, if applicable.
        context_snapshot: Available metrics at time of failure.
        details: Structured details about the failure.
        recovery_hint: Guidance on how to resolve the issue.
        fail_closed: Whether the system should BLOCK on this error (default True).
    """

    def __init__(
        self,
        message: str,
        category: PolicyExceptionCategory = PolicyExceptionCategory.UNKNOWN,
        policy_id: str = "",
        version_id: str = "",
        rule_id: str = "",
        rule_set_id: str = "",
        context_snapshot: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
        recovery_hint: str = "",
        fail_closed: bool = True,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.category = category
        self.policy_id = policy_id
        self.version_id = version_id
        self.rule_id = rule_id
        self.rule_set_id = rule_set_id
        self.context_snapshot = context_snapshot or {}
        self.details = details or {}
        self.recovery_hint = recovery_hint
        self.fail_closed = fail_closed
        self.cause = cause
        self.timestamp = time.time()
        self.traceback = traceback.format_exc()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def category_name(self) -> str:
        return self.category.name

    @property
    def is_technical(self) -> bool:
        """Whether this is a technical failure vs. a business rule violation."""
        return self.category in (
            PolicyExceptionCategory.EVALUATION_ERROR,
            PolicyExceptionCategory.METRIC_UNAVAILABLE,
            PolicyExceptionCategory.CONTEXT_INVALID,
            PolicyExceptionCategory.EXPRESSION_ERROR,
            PolicyExceptionCategory.STORAGE_ERROR,
            PolicyExceptionCategory.CACHE_ERROR,
            PolicyExceptionCategory.LOAD_ERROR,
        )

    @property
    def is_lifecycle(self) -> bool:
        return self.category in (
            PolicyExceptionCategory.VERSION_INVALID,
            PolicyExceptionCategory.TRANSITION_FAILED,
            PolicyExceptionCategory.IMMUTABLE_VIOLATION,
        )

    @property
    def is_integrity(self) -> bool:
        return self.category in (
            PolicyExceptionCategory.CHECKSUM_MISMATCH,
            PolicyExceptionCategory.TAMPER_DETECTED,
            PolicyExceptionCategory.SIGNATURE_INVALID,
        )

    @property
    def source_location(self) -> str:
        """Formatted source location: policy_id@version_id:rule_id."""
        parts = []
        if self.policy_id:
            parts.append(self.policy_id)
            if self.version_id:
                parts.append(f"@{self.version_id}")
        if self.rule_id:
            parts.append(f":{self.rule_id}")
        return "".join(parts)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message": str(self),
            "category": self.category_name,
            "policy_id": self.policy_id,
            "version_id": self.version_id,
            "rule_id": self.rule_id,
            "rule_set_id": self.rule_set_id,
            "source_location": self.source_location,
            "context_snapshot": self.context_snapshot,
            "details": self.details,
            "recovery_hint": self.recovery_hint,
            "fail_closed": self.fail_closed,
            "is_technical": self.is_technical,
            "is_lifecycle": self.is_lifecycle,
            "is_integrity": self.is_integrity,
            "cause": str(self.cause) if self.cause else None,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyException":
        return cls(
            message=data.get("message", ""),
            category=PolicyExceptionCategory[
                data.get("category", "UNKNOWN")
            ],
            policy_id=data.get("policy_id", ""),
            version_id=data.get("version_id", ""),
            rule_id=data.get("rule_id", ""),
            rule_set_id=data.get("rule_set_id", ""),
            context_snapshot=data.get("context_snapshot", {}),
            details=data.get("details", {}),
            recovery_hint=data.get("recovery_hint", ""),
            fail_closed=data.get("fail_closed", True),
        )


# ---------------------------------------------------------------------------
# Specific exceptions
# ---------------------------------------------------------------------------

class MetricUnavailableException(PolicyException):
    """Required metric was not found in the evaluation context."""

    def __init__(self, metric: str, policy_id: str = "", **kwargs):
        super().__init__(
            message=f"Metric '{metric}' unavailable for policy evaluation",
            category=PolicyExceptionCategory.METRIC_UNAVAILABLE,
            policy_id=policy_id,
            recovery_hint=f"Ensure metric '{metric}' is provided in the evaluation context.",
            **kwargs,
        )


class VersionInvalidException(PolicyException):
    """Policy version is not in a valid state for the requested operation."""

    def __init__(
        self,
        version_id: str,
        current_status: str,
        expected_status: str,
        **kwargs,
    ):
        super().__init__(
            message=f"Version '{version_id}' is {current_status}, "
                    f"expected {expected_status}",
            category=PolicyExceptionCategory.VERSION_INVALID,
            version_id=version_id,
            recovery_hint=f"Transition version to {expected_status} before proceeding.",
            **kwargs,
        )


class ImmutableViolationException(PolicyException):
    """Attempt to modify a published/immutable policy version."""

    def __init__(self, version_id: str, status: str, **kwargs):
        super().__init__(
            message=f"Cannot modify version '{version_id}': "
                    f"version is immutable (status={status})",
            category=PolicyExceptionCategory.IMMUTABLE_VIOLATION,
            version_id=version_id,
            recovery_hint="Create a new draft version to make changes.",
            **kwargs,
        )


class ChecksumMismatchException(PolicyException):
    """Policy content hash does not match the stored checksum."""

    def __init__(self, version_id: str, policy_id: str = "", **kwargs):
        super().__init__(
            message=f"Checksum mismatch for version '{version_id}' — "
                    f"content may have been tampered",
            category=PolicyExceptionCategory.CHECKSUM_MISMATCH,
            version_id=version_id,
            policy_id=policy_id,
            recovery_hint="Re-publish the policy from a trusted source.",
            fail_closed=True,
            **kwargs,
        )


class DependencyCycleException(PolicyException):
    """Circular dependency detected in policy dependency graph."""

    def __init__(self, cycle: List[str], **kwargs):
        cycle_str = " → ".join(cycle)
        super().__init__(
            message=f"Circular dependency detected: {cycle_str}",
            category=PolicyExceptionCategory.DEPENDENCY_CYCLE,
            details={"cycle": cycle},
            recovery_hint="Break the dependency cycle by removing one of the dependencies.",
            **kwargs,
        )


class EvaluationLoopException(PolicyException):
    """Infinite loop detected in rule evaluation (self-referencing rules)."""

    def __init__(self, policy_id: str, rule_id: str, depth: int, **kwargs):
        super().__init__(
            message=f"Evaluation loop detected in policy '{policy_id}', "
                    f"rule '{rule_id}' at depth {depth}",
            category=PolicyExceptionCategory.RULE_LOOP_DETECTED,
            policy_id=policy_id,
            rule_id=rule_id,
            details={"depth": depth},
            recovery_hint="Remove or refactor the self-referencing rule.",
            **kwargs,
        )


class TransitionFailedException(PolicyException):
    """Lifecycle transition was rejected by the state machine."""

    def __init__(
        self,
        version_id: str,
        from_status: str,
        to_status: str,
        **kwargs,
    ):
        super().__init__(
            message=f"Transition {from_status} → {to_status} failed "
                    f"for version '{version_id}'",
            category=PolicyExceptionCategory.TRANSITION_FAILED,
            version_id=version_id,
            details={"from": from_status, "to": to_status},
            **kwargs,
        )


class PolicyLoadException(PolicyException):
    """Failed to load policy from repository/storage."""

    def __init__(
        self,
        policy_id: str,
        version_id: str = "",
        storage_error: str = "",
        **kwargs,
    ):
        super().__init__(
            message=f"Failed to load policy '{policy_id}'"
                    + (f" version '{version_id}'" if version_id else ""),
            category=PolicyExceptionCategory.LOAD_ERROR,
            policy_id=policy_id,
            version_id=version_id,
            details={"storage_error": storage_error},
            recovery_hint="Check repository connectivity and policy file integrity.",
            **kwargs,
        )


# ---------------------------------------------------------------------------
# Exception handler / collector
# ---------------------------------------------------------------------------

@dataclass
class PolicyExceptionCollector:
    """
    Collects and aggregates policy exceptions during evaluation runs.

    Used in batch evaluation to capture all errors without stopping
    evaluation of other policies (non-fatal collection).
    """

    exceptions: List[PolicyException] = field(default_factory=list)

    def add(self, exc: PolicyException) -> None:
        self.exceptions.append(exc)

    @property
    def count(self) -> int:
        return len(self.exceptions)

    @property
    def has_fatal(self) -> bool:
        """Whether any collected exception is fail-closed."""
        return any(e.fail_closed for e in self.exceptions)

    @property
    def blocking_policies(self) -> List[str]:
        """Policy IDs with fail-closed exceptions."""
        return [
            e.policy_id for e in self.exceptions
            if e.fail_closed and e.policy_id
        ]

    def by_category(self) -> Dict[str, List[PolicyException]]:
        """Group exceptions by category."""
        grouped: Dict[str, List[PolicyException]] = {}
        for exc in self.exceptions:
            cat = exc.category_name
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(exc)
        return grouped

    def summary(self) -> Dict[str, Any]:
        """Summary of collected exceptions."""
        return {
            "total": self.count,
            "has_fatal": self.has_fatal,
            "blocking_policies": self.blocking_policies,
            "by_category": {
                cat: len(excs) for cat, excs in self.by_category().items()
            },
            "exceptions": [e.to_dict() for e in self.exceptions],
        }

    def clear(self) -> None:
        self.exceptions.clear()
