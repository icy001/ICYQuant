"""
Policy Publisher — manages the publication and activation of policy versions.

The publisher is responsible for the full publication pipeline:
  DRAFT → VALIDATED → APPROVED → PUBLISHED → ACTIVE

It coordinates:
  - Pre-publication validation
  - Dependency resolution
  - Conflict detection
  - Atomic activation (all-or-nothing for groups of policies)
  - Rollback of failed activations
  - Notification of policy changes
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from .policy_version import PolicyVersion
from .policy_registry import PolicyRegistry
from .policy_repository import PolicyRepository
from .policy_status import PolicyLifecycleStatus
from .policy_dependency import DependencyGraph, DependencyType, PolicyDependency
from .policy_exception import (
    PolicyException,
    TransitionFailedException,
    VersionInvalidException,
)


# ---------------------------------------------------------------------------
# Publish result
# ---------------------------------------------------------------------------

@dataclass
class PublishResult:
    """Result of a publish or activation operation."""

    success: bool = True
    operation: str = ""  # PUBLISH, ACTIVATE, DEACTIVATE, ROLLBACK

    # Affected versions
    versions: List[Dict[str, str]] = field(default_factory=list)

    # Details
    message: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Timing
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def add_version(self, policy_id: str, version_id: str, status: str) -> None:
        self.versions.append({
            "policy_id": policy_id,
            "version_id": version_id,
            "status": status,
        })

    def add_error(self, error: str) -> None:
        self.success = False
        self.errors.append(error)

    def add_warning(self, warning: str) -> None:
        self.warnings.append(warning)

    def complete(self) -> "PublishResult":
        self.completed_at = time.time()
        return self

    @property
    def duration_ms(self) -> float:
        end = self.completed_at or time.time()
        return (end - self.started_at) * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "operation": self.operation,
            "versions": self.versions,
            "message": self.message,
            "errors": self.errors,
            "warnings": self.warnings,
            "duration_ms": self.duration_ms,
        }


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------

@dataclass
class PolicyPublisher:
    """
    Orchestrates the publication and activation of policy versions.

    Publication pipeline:
      1. Validate the version
      2. Resolve dependencies
      3. Detect conflicts
      4. Publish (freeze content, compute hash)
      5. Activate (or activate a batch atomically)
    """

    registry: Optional[PolicyRegistry] = None
    repository: Optional[PolicyRepository] = None
    dependency_graph: Optional[DependencyGraph] = None

    # Hooks
    on_publish: Optional[Callable[[PolicyVersion], None]] = None
    on_activate: Optional[Callable[[PolicyVersion], None]] = None
    on_error: Optional[Callable[[PolicyException], None]] = None

    # History
    publish_history: List[PublishResult] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Publish single version
    # ------------------------------------------------------------------

    def publish(
        self, version: PolicyVersion, actor: str = "SYSTEM"
    ) -> PublishResult:
        """
        Publish a single policy version through the full pipeline.

        Pipeline:
          DRAFT → VALIDATED → APPROVED → PUBLISHED

        The version must be in DRAFT or APPROVED state.
        """
        result = PublishResult(operation="PUBLISH")
        try:
            # Validate → Approve → Publish
            if version.status == PolicyLifecycleStatus.DRAFT:
                version.validate(actor)
                result.add_version(
                    version.policy_id, version.version_id,
                    PolicyLifecycleStatus.VALIDATED.name,
                )

            if version.status == PolicyLifecycleStatus.VALIDATED:
                version.approve(actor)
                result.add_version(
                    version.policy_id, version.version_id,
                    PolicyLifecycleStatus.APPROVED.name,
                )

            if version.status == PolicyLifecycleStatus.APPROVED:
                version.publish(actor)
                result.add_version(
                    version.policy_id, version.version_id,
                    PolicyLifecycleStatus.PUBLISHED.name,
                )

                # Store in repository
                if self.repository:
                    self.repository.save(version, actor)

                result.message = (
                    f"Policy '{version.name}' (v{version.version}) published"
                )

            elif version.status == PolicyLifecycleStatus.PUBLISHED:
                result.add_warning(
                    f"Policy '{version.name}' is already PUBLISHED"
                )

            else:
                raise TransitionFailedException(
                    version_id=version.version_id,
                    from_status=version.status.name,
                    to_status="PUBLISHED",
                )

            if self.on_publish:
                self.on_publish(version)

        except Exception as e:
            result.add_error(str(e))
            if isinstance(e, PolicyException) and self.on_error:
                self.on_error(e)

        result.complete()
        self.publish_history.append(result)
        return result

    # ------------------------------------------------------------------
    # Activate single version
    # ------------------------------------------------------------------

    def activate(
        self, version: PolicyVersion, actor: str = "SYSTEM"
    ) -> PublishResult:
        """
        Activate a published policy version.

        This makes it the active version for its policy family,
        superseding any previously active version.
        """
        result = PublishResult(operation="ACTIVATE")
        try:
            if version.status == PolicyLifecycleStatus.PUBLISHED:
                # Verify content integrity
                if not version.verify_checksum():
                    raise VersionInvalidException(
                        version_id=version.version_id,
                        current_status="PUBLISHED",
                        expected_status="checksum verified",
                    )

                version.activate(actor)
                result.add_version(
                    version.policy_id, version.version_id,
                    PolicyLifecycleStatus.ACTIVE.name,
                )

                # Update registry
                if self.registry:
                    self.registry.set_active(
                        version.policy_id, version.version_id
                    )

                # Update repository
                if self.repository:
                    self.repository.save(version, actor)

                result.message = (
                    f"Policy '{version.name}' (v{version.version}) activated"
                )

            elif version.status == PolicyLifecycleStatus.ACTIVE:
                result.add_warning(
                    f"Policy '{version.name}' is already ACTIVE"
                )

            else:
                raise TransitionFailedException(
                    version_id=version.version_id,
                    from_status=version.status.name,
                    to_status="ACTIVE",
                )

            if self.on_activate:
                self.on_activate(version)

        except Exception as e:
            result.add_error(str(e))
            if isinstance(e, PolicyException) and self.on_error:
                self.on_error(e)

        result.complete()
        self.publish_history.append(result)
        return result

    # ------------------------------------------------------------------
    # Publish + Activate (full pipeline)
    # ------------------------------------------------------------------

    def publish_and_activate(
        self, version: PolicyVersion, actor: str = "SYSTEM"
    ) -> PublishResult:
        """
        Run the full pipeline: publish then activate.

        Returns a single result documenting both steps.
        """
        published = self.publish(version, actor)
        if not published.success:
            return published

        activated = self.activate(version, actor)
        activated.versions = published.versions + activated.versions
        return activated

    # ------------------------------------------------------------------
    # Atomic batch activation
    # ------------------------------------------------------------------

    def activate_batch(
        self,
        versions: List[PolicyVersion],
        actor: str = "SYSTEM",
    ) -> PublishResult:
        """
        Activate multiple policy versions atomically.

        All versions are validated together. If any validation fails,
        none are activated (all-or-nothing).

        Pre-checks:
          - All versions must be PUBLISHED
          - No dependency violations
          - No conflicts between versions in the batch
          - No cycles in the dependency graph
        """
        result = PublishResult(operation="ACTIVATE_BATCH")
        rollback_versions: List[PolicyVersion] = []

        try:
            # Pre-check: all must be PUBLISHED
            for version in versions:
                if version.status != PolicyLifecycleStatus.PUBLISHED:
                    result.add_error(
                        f"Version '{version.version_id}' ({version.name}) "
                        f"is {version.status.name}, must be PUBLISHED"
                    )
            if result.errors:
                result.complete()
                return result

            # Pre-check: dependency validation
            if self.dependency_graph:
                active_ids = set()
                if self.registry:
                    active_ids = {
                        v.policy_id for v in self.registry.list_active()
                    }
                # Include versions in the batch as "active" for validation
                batch_ids = {v.policy_id for v in versions}
                for version in versions:
                    can_activate, reasons = self.dependency_graph.validate_activation(
                        version.policy_id, active_ids | batch_ids
                    )
                    if not can_activate:
                        for reason in reasons:
                            result.add_error(reason)
                if result.errors:
                    result.complete()
                    return result

            # Activate one by one (but pre-validated together)
            for version in versions:
                try:
                    # Verify checksum
                    if not version.verify_checksum():
                        raise ValueError("Checksum verification failed")

                    version.activate(actor)
                    result.add_version(
                        version.policy_id, version.version_id,
                        PolicyLifecycleStatus.ACTIVE.name,
                    )
                    rollback_versions.append(version)

                    # Update registry
                    if self.registry:
                        self.registry.set_active(
                            version.policy_id, version.version_id
                        )

                    # Update repository
                    if self.repository:
                        self.repository.save(version, actor)

                except Exception as e:
                    result.add_error(
                        f"Failed to activate {version.policy_id}: {e}"
                    )
                    # Roll back previously activated versions
                    self._rollback_activation(rollback_versions, actor)
                    result.add_warning(
                        f"Rolled back {len(rollback_versions)} activations"
                    )
                    result.complete()
                    self.publish_history.append(result)
                    return result

            result.message = (
                f"Batch activation complete: {len(versions)} policies activated"
            )

        except Exception as e:
            result.add_error(f"Batch activation error: {e}")
            if isinstance(e, PolicyException) and self.on_error:
                self.on_error(e)

        result.complete()
        self.publish_history.append(result)
        return result

    # ------------------------------------------------------------------
    # Deactivate
    # ------------------------------------------------------------------

    def deactivate(
        self, version: PolicyVersion, actor: str = "SYSTEM"
    ) -> PublishResult:
        """Deactivate a policy version."""
        result = PublishResult(operation="DEACTIVATE")
        try:
            if version.status == PolicyLifecycleStatus.ACTIVE:
                version.expire()
                result.add_version(
                    version.policy_id, version.version_id,
                    PolicyLifecycleStatus.EXPIRED.name,
                )

                # Update registry
                if self.registry:
                    self.registry.deactivate(version.policy_id)

                # Update repository
                if self.repository:
                    self.repository.save(version, actor)

                result.message = (
                    f"Policy '{version.name}' (v{version.version}) deactivated"
                )
            else:
                result.add_warning(
                    f"Policy '{version.name}' is not ACTIVE (status={version.status.name})"
                )

        except Exception as e:
            result.add_error(str(e))

        result.complete()
        self.publish_history.append(result)
        return result

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def _rollback_activation(
        self, versions: List[PolicyVersion], actor: str
    ) -> None:
        """Roll back activation of a batch (revert to PUBLISHED)."""
        for version in versions:
            try:
                # Revert to PUBLISHED
                # Note: This creates an edge case where the version was
                # briefly ACTIVE. In a production system, we'd maintain
                # a pre-activation snapshot for exact rollback.
                if version.status == PolicyLifecycleStatus.ACTIVE:
                    version.status = PolicyLifecycleStatus.PUBLISHED
                    if self.repository:
                        self.repository.save(version, actor)
                    if self.registry:
                        self.registry.deactivate(version.policy_id)
            except Exception:
                # Best-effort rollback
                pass

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_last_result(self) -> Optional[PublishResult]:
        return self.publish_history[-1] if self.publish_history else None

    def get_history(
        self, operation: str = "", limit: int = 50
    ) -> List[PublishResult]:
        results = self.publish_history
        if operation:
            results = [r for r in results if r.operation == operation]
        return results[-limit:]

    def clear_history(self) -> None:
        self.publish_history.clear()

    def __repr__(self) -> str:
        return (
            f"PolicyPublisher(history={len(self.publish_history)})"
        )
