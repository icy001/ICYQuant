"""
Policy Activator — controls policy version activation with safety checks.

The activator is the gatekeeper for putting policy versions into effect.
All activations go through the activator to ensure:

  - Version is in PUBLISHED state
  - Content integrity is verified (checksum)
  - Dependencies are satisfied
  - No conflicts with currently active policies
  - Atomic activation of interdependent policies
  - Previous versions are properly superseded
  - Full audit trail of activation events
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .policy_version import PolicyVersion
from .policy_registry import PolicyRegistry
from .policy_repository import PolicyRepository
from .policy_status import PolicyLifecycleStatus
from .policy_dependency import DependencyGraph
from .policy_exception import (
    PolicyException,
    VersionInvalidException,
    ChecksumMismatchException,
    TransitionFailedException,
)


# ---------------------------------------------------------------------------
# Activation result
# ---------------------------------------------------------------------------

@dataclass
class ActivationResult:
    """Result of an activation attempt."""

    success: bool = True
    policy_id: str = ""
    version_id: str = ""
    version: str = ""
    policy_name: str = ""

    # Status
    from_status: str = ""
    to_status: str = ""
    superseded_version: Optional[str] = None

    # Checks
    checksum_verified: bool = False
    dependencies_satisfied: bool = True
    conflicts_resolved: bool = True

    # Errors
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Timing
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def add_error(self, error: str) -> None:
        self.success = False
        self.errors.append(error)

    def add_warning(self, warning: str) -> None:
        self.warnings.append(warning)

    def complete(self) -> "ActivationResult":
        self.completed_at = time.time()
        return self

    @property
    def duration_ms(self) -> float:
        end = self.completed_at or time.time()
        return (end - self.started_at) * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "policy_id": self.policy_id,
            "version_id": self.version_id,
            "version": self.version,
            "policy_name": self.policy_name,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "superseded_version": self.superseded_version,
            "checksum_verified": self.checksum_verified,
            "dependencies_satisfied": self.dependencies_satisfied,
            "conflicts_resolved": self.conflicts_resolved,
            "errors": self.errors,
            "warnings": self.warnings,
            "duration_ms": self.duration_ms,
        }


# ---------------------------------------------------------------------------
# Activator
# ---------------------------------------------------------------------------

@dataclass
class PolicyActivator:
    """
    Controls activation of policy versions.

    Performs safety checks before putting a version into effect:
      1. Version integrity (checksum)
      2. Lifecycle check (must be PUBLISHED)
      3. Dependency validation
      4. Conflict detection
      5. Atomic activation with supersede of previous versions
    """

    registry: Optional[PolicyRegistry] = None
    repository: Optional[PolicyRepository] = None
    dependency_graph: Optional[DependencyGraph] = None

    # Configuration
    require_checksum: bool = True
    require_dependencies: bool = True
    require_conflict_check: bool = True
    auto_supersede: bool = True

    # History
    activation_history: List[ActivationResult] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Activate single version
    # ------------------------------------------------------------------

    def activate(
        self,
        version: PolicyVersion,
        actor: str = "SYSTEM",
    ) -> ActivationResult:
        """
        Activate a policy version with full safety checks.

        Steps:
          1. Verify lifecycle status (must be PUBLISHED)
          2. Verify content integrity (checksum)
          3. Check dependencies
          4. Detect conflicts
          5. Perform activation (supersede old version)
          6. Update registry and repository
        """
        result = ActivationResult(
            policy_id=version.policy_id,
            version_id=version.version_id,
            version=version.version,
            policy_name=version.name,
            from_status=version.status.name,
        )

        try:
            # ---- Step 1: Lifecycle check ----
            if version.status != PolicyLifecycleStatus.PUBLISHED:
                result.add_error(
                    f"Version must be PUBLISHED to activate, "
                    f"current status: {version.status.name}"
                )
                result.complete()
                return result

            # ---- Step 2: Checksum verification ----
            if self.require_checksum:
                if not version.verify_checksum():
                    result.add_error(
                        f"Checksum verification failed for version {version.version_id}"
                    )
                    result.complete()
                    return result
                result.checksum_verified = True

            # ---- Step 3: Dependency validation ----
            if self.require_dependencies and self.dependency_graph:
                active_ids = set()
                if self.registry:
                    active_ids = {
                        v.policy_id
                        for v in self.registry.list_active()
                        if v.policy_id != version.policy_id
                    }

                can_activate, reasons = self.dependency_graph.validate_activation(
                    version.policy_id, active_ids
                )
                if not can_activate:
                    for reason in reasons:
                        result.add_error(reason)
                    result.dependencies_satisfied = False
                    result.complete()
                    return result

            # ---- Step 4: Conflict detection ----
            if self.require_conflict_check:
                conflicts = self._find_conflicts(version)
                if conflicts:
                    for conflict in conflicts:
                        result.add_error(conflict)
                    result.conflicts_resolved = False
                    result.complete()
                    return result

            # ---- Step 5: Perform activation ----
            previous_active_id = self._get_previous_active(version.policy_id)
            version.activate(actor)
            result.to_status = PolicyLifecycleStatus.ACTIVE.name

            # Supersede previous version
            if self.auto_supersede and previous_active_id:
                previous_version = self._get_version(
                    version.policy_id, previous_active_id
                )
                if previous_version and previous_version.status == PolicyLifecycleStatus.ACTIVE:
                    previous_version.supersede(version.version_id, actor)
                    result.superseded_version = previous_active_id

                    # Update repository for superseded version
                    if self.repository:
                        self.repository.save(previous_version, actor)

            # ---- Step 6: Update registry and repository ----
            if self.registry:
                self.registry.set_active(version.policy_id, version.version_id)

            if self.repository:
                self.repository.save(version, actor)

            result.success = True

        except (PolicyException, ValueError) as e:
            result.add_error(str(e))

        except Exception as e:
            result.add_error(f"Unexpected activation error: {e}")

        result.complete()
        self.activation_history.append(result)
        return result

    # ------------------------------------------------------------------
    # Activate batch
    # ------------------------------------------------------------------

    def activate_batch(
        self,
        versions: List[PolicyVersion],
        actor: str = "SYSTEM",
    ) -> List[ActivationResult]:
        """
        Activate multiple versions atomically.

        All-or-nothing: if any activation fails, all are rolled back.
        """
        results: List[ActivationResult] = []
        activated: List[PolicyVersion] = []

        # Pre-validate all
        all_valid = True
        for version in versions:
            pre_check = self._pre_validate(version)
            if not pre_check.success:
                all_valid = False
                results.append(pre_check)

        if not all_valid:
            return results

        # Activate one by one
        for version in versions:
            result = self.activate(version, actor)
            results.append(result)
            if not result.success:
                # Rollback
                self._rollback_batch(activated, actor)
                return results
            activated.append(version)

        return results

    def _pre_validate(self, version: PolicyVersion) -> ActivationResult:
        """Quick pre-validation without performing activation."""
        result = ActivationResult(
            policy_id=version.policy_id,
            version_id=version.version_id,
            version=version.version,
            policy_name=version.name,
            from_status=version.status.name,
        )

        if version.status != PolicyLifecycleStatus.PUBLISHED:
            result.add_error(
                f"Must be PUBLISHED, current: {version.status.name}"
            )
        if self.require_checksum and not version.verify_checksum():
            result.add_error("Checksum verification failed")
            result.checksum_verified = False

        return result

    # ------------------------------------------------------------------
    # Deactivate
    # ------------------------------------------------------------------

    def deactivate(
        self,
        version: PolicyVersion,
        actor: str = "SYSTEM",
    ) -> ActivationResult:
        """
        Deactivate a policy version.

        Checks that no other active policies depend on this one.
        """
        result = ActivationResult(
            policy_id=version.policy_id,
            version_id=version.version_id,
            version=version.version,
            policy_name=version.name,
            from_status=version.status.name,
        )

        try:
            if version.status != PolicyLifecycleStatus.ACTIVE:
                result.add_error(
                    f"Cannot deactivate: version is {version.status.name}, not ACTIVE"
                )
                result.complete()
                return result

            # Check dependents
            if self.dependency_graph:
                active_ids = (
                    {v.policy_id for v in self.registry.list_active()}
                    if self.registry else set()
                )
                # Remove self
                active_ids.discard(version.policy_id)

                can_deactivate, reasons = self.dependency_graph.validate_deactivation(
                    version.policy_id, active_ids
                )
                if not can_deactivate:
                    for reason in reasons:
                        result.add_error(reason)
                    result.complete()
                    return result

            # Perform deactivation
            version.expire()
            result.to_status = PolicyLifecycleStatus.EXPIRED.name

            if self.registry:
                self.registry.deactivate(version.policy_id)

            if self.repository:
                self.repository.save(version, actor)

        except Exception as e:
            result.add_error(str(e))

        result.complete()
        self.activation_history.append(result)
        return result

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------

    def _find_conflicts(self, version: PolicyVersion) -> List[str]:
        """Find conflicts between this version and currently active versions."""
        conflicts: List[str] = []

        if not self.registry:
            return conflicts

        active = self.registry.list_active()
        for active_version in active:
            if active_version.policy_id == version.policy_id:
                continue
            if active_version.scope == version.scope:
                # Same scope, check if they conflict
                if self.dependency_graph:
                    for dep in self.dependency_graph.get_conflicts(version.policy_id):
                        if dep.target_policy_id == active_version.policy_id:
                            conflicts.append(
                                f"CONFLICTS_WITH active policy '{active_version.name}' "
                                f"({active_version.policy_id}): {dep.reason}"
                            )

        return conflicts

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_previous_active(self, policy_id: str) -> Optional[str]:
        if self.registry:
            active_version = self.registry.get_active(policy_id)
            if active_version:
                return active_version.version_id
        return None

    def _get_version(
        self, policy_id: str, version_id: str
    ) -> Optional[PolicyVersion]:
        if self.registry:
            return self.registry.get(policy_id, version_id)
        if self.repository:
            return self.repository.load(policy_id, version_id)
        return None

    def _rollback_batch(
        self, activated: List[PolicyVersion], actor: str
    ) -> None:
        """Rollback a batch activation."""
        for version in reversed(activated):
            try:
                version.status = PolicyLifecycleStatus.PUBLISHED
                if self.registry:
                    self.registry.deactivate(version.policy_id)
                if self.repository:
                    self.repository.save(version, actor)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_history(self, limit: int = 50) -> List[ActivationResult]:
        return self.activation_history[-limit:]

    def get_last_activation(self) -> Optional[ActivationResult]:
        return self.activation_history[-1] if self.activation_history else None

    def clear_history(self) -> None:
        self.activation_history.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "history": [r.to_dict() for r in self.activation_history],
            "require_checksum": self.require_checksum,
            "require_dependencies": self.require_dependencies,
            "require_conflict_check": self.require_conflict_check,
            "auto_supersede": self.auto_supersede,
        }

    def __repr__(self) -> str:
        return (
            f"PolicyActivator(history={len(self.activation_history)}, "
            f"checksum={self.require_checksum})"
        )
