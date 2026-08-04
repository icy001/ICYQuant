"""
Snapshot integrity verification.

Verifies the integrity of configuration snapshots
through:
- Checksum verification (SHA-256)
- Hash comparison
- Version chain validation
- Signature verification (reserved)

Usage:
    integrity = SnapshotIntegrity()
    result = integrity.verify(snapshot)
    if result.valid:
        # Snapshot is safe to use
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .dynamic.snapshot import DynamicSnapshot


class IntegrityResult:
    """
    Result of an integrity check.

    Attributes:
        valid: Whether the snapshot passed all checks.
        checksum_valid: Whether the checksum matches.
        version_valid: Whether the version chain is valid.
        errors: List of error messages.
        checksum: Snapshot checksum.
        version: Snapshot version.
    """

    def __init__(
        self,
        valid: bool,
        checksum_valid: bool = True,
        version_valid: bool = True,
        errors: Optional[List[str]] = None,
        checksum: str = "",
        version: int = 0,
    ) -> None:
        self.valid = valid
        self.checksum_valid = checksum_valid
        self.version_valid = version_valid
        self.errors = errors or []
        self.checksum = checksum
        self.version = version
        self.verified_at = datetime.utcnow()

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "checksum_valid": self.checksum_valid,
            "version_valid": self.version_valid,
            "errors": self.errors,
            "checksum": self.checksum,
            "version": self.version,
            "verified_at": self.verified_at.isoformat(),
        }


class SnapshotIntegrity:
    """
    Snapshot integrity verifier.

    Performs comprehensive integrity checks on
    configuration snapshots to ensure they haven't
    been corrupted or tampered with.

    Checks:
    1. Checksum: SHA-256 hash verification
    2. Version: Monotonic version chain
    3. Structure: Required fields present
    4. Consistency: Internal data consistency

    Usage:
        integrity = SnapshotIntegrity()
        result = integrity.verify(snapshot)
        if not result.valid:
            for error in result.errors:
                print(f"Integrity error: {error}")
    """

    def __init__(
        self,
        enable_signature: bool = False,
    ) -> None:
        """
        Initialize integrity verifier.

        Args:
            enable_signature: Enable signature verification (reserved).
        """
        self._enable_signature = enable_signature
        self._verification_history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def verify(
        self,
        snapshot: DynamicSnapshot,
    ) -> IntegrityResult:
        """
        Verify snapshot integrity.

        Args:
            snapshot: Snapshot to verify.

        Returns:
            IntegrityResult.
        """
        errors: List[str] = []

        # Check 1: Checksum verification
        checksum_valid = snapshot.verify_integrity()
        if not checksum_valid:
            errors.append("Checksum verification failed: data may be corrupted")

        # Check 2: Version chain
        version_valid = True
        if snapshot.parent_version is not None:
            if snapshot.parent_version >= snapshot.version:
                version_valid = False
                errors.append(
                    f"Version chain invalid: parent {snapshot.parent_version} "
                    f">= current {snapshot.version}"
                )

        # Check 3: Structure
        if not snapshot.values:
            errors.append("Snapshot contains no values")
        if not snapshot.environment:
            errors.append("Snapshot missing environment")

        # Check 4: Consistency
        if snapshot.version < 0:
            errors.append(f"Invalid version number: {snapshot.version}")

        valid = len(errors) == 0 and checksum_valid and version_valid

        result = IntegrityResult(
            valid=valid,
            checksum_valid=checksum_valid,
            version_valid=version_valid,
            errors=errors,
            checksum=snapshot.checksum,
            version=snapshot.version,
        )

        # Record verification
        self._record_verification(result)

        return result

    def verify_chain(
        self,
        snapshots: List[DynamicSnapshot],
    ) -> IntegrityResult:
        """
        Verify a chain of snapshots.

        Args:
            snapshots: List of snapshots in order.

        Returns:
            IntegrityResult for the chain.
        """
        if not snapshots:
            return IntegrityResult(
                valid=False,
                errors=["No snapshots to verify"],
            )

        errors: List[str] = []

        for i, snapshot in enumerate(snapshots):
            result = self.verify(snapshot)
            if not result.valid:
                errors.extend(
                    f"Snapshot v{snapshot.version}: {e}" for e in result.errors
                )

            # Check chain continuity
            if i > 0:
                prev = snapshots[i - 1]
                if snapshot.parent_version != prev.version:
                    errors.append(
                        f"Chain broken: v{snapshot.version} parent "
                        f"({snapshot.parent_version}) != prev ({prev.version})"
                    )

        valid = len(errors) == 0

        return IntegrityResult(
            valid=valid,
            errors=errors,
            version=snapshots[-1].version,
        )

    def calculate_checksum(
        self,
        data: Dict[str, Any],
    ) -> str:
        """
        Calculate checksum for arbitrary configuration data.

        Args:
            data: Configuration data.

        Returns:
            SHA-256 checksum.
        """
        normalized = json.dumps(
            self._sort_dict(data),
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(normalized.encode()).hexdigest()

    @staticmethod
    def _sort_dict(
        d: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Recursively sort dictionary."""
        return {
            k: SnapshotIntegrity._sort_dict(v) if isinstance(v, dict) else v
            for k, v in sorted(d.items())
        }

    def _record_verification(
        self,
        result: IntegrityResult,
    ) -> None:
        """Record a verification event."""
        with self._lock:
            self._verification_history.append(result.to_dict())
            if len(self._verification_history) > 1000:
                self._verification_history.pop(0)

    def get_history(
        self,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get verification history."""
        with self._lock:
            return self._verification_history[-limit:]

    def get_stats(
        self,
    ) -> Dict[str, Any]:
        """Get verification statistics."""
        with self._lock:
            total = len(self._verification_history)
            if total == 0:
                return {"total_verifications": 0}

            passed = sum(
                1 for r in self._verification_history if r["valid"]
            )
            return {
                "total_verifications": total,
                "passed": passed,
                "failed": total - passed,
                "pass_rate": passed / total if total > 0 else 0,
            }
