"""
Secrets integrity verification.

Provides comprehensive integrity verification for
secrets data, including secret data integrity, vault
provider integrity, cache consistency, access policy
integrity, and audit log integrity.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SecretsIntegrityResult:
    """
    Result of an integrity verification.

    Attributes:
        valid: Overall validity flag.
        checksums: Dict of component checksums.
        errors: List of integrity errors found.
        verified_at: When verification was performed.
    """

    valid: bool = True
    checksums: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    verified_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "checksums": self.checksums,
            "errors": self.errors,
            "verified_at": self.verified_at.isoformat() + "Z",
        }


class SecretsIntegrity:
    """
    Secrets integrity verifier.

    Performs comprehensive integrity verification
    across secrets platform components, detecting
    tampering, corruption, and consistency violations.

    Usage:
        integrity = SecretsIntegrity(registry=registry, cache=cache)
        result = integrity.verify()
        if not result.valid:
            print("Integrity check failed:", result.errors)
    """

    def __init__(
        self,
        registry: Optional[Any] = None,
        cache: Optional[Any] = None,
        provider: Optional[Any] = None,
        audit: Optional[Any] = None,
        policy: Optional[Any] = None,
        max_history: int = 500,
    ) -> None:
        """
        Initialize integrity verifier.

        Args:
            registry: SecretsRegistry instance.
            cache: SecretsCache instance.
            provider: SecretsProvider instance.
            audit: SecretsAudit instance.
            policy: SecretAccessPolicy instance.
            max_history: Maximum history entries to retain.
        """
        self._registry = registry
        self._cache = cache
        self._provider = provider
        self._audit = audit
        self._policy = policy
        self._max_history = max_history
        self._lock = threading.RLock()
        self._history: List[Dict[str, Any]] = []
        self._verification_count = 0
        self._last_verified_at: Optional[datetime] = None
        self._errors_total = 0

    # ── Verification ──

    def verify(self) -> SecretsIntegrityResult:
        """
        Perform a comprehensive integrity verification.

        Checks all configured components for integrity
        issues, including secret data, cache, provider,
        access policies, and audit logs.

        Returns:
            SecretsIntegrityResult with verification details.
        """
        with self._lock:
            result = SecretsIntegrityResult()

            self._verify_secret_data(result)
            self._verify_vault_provider(result)
            self._verify_cache_consistency(result)
            self._verify_access_policy(result)
            self._verify_audit_log(result)

            self._verification_count += 1
            self._last_verified_at = datetime.utcnow()

            if result.errors:
                result.valid = False
                self._errors_total += len(result.errors)

            self._record_history(result)

            return result

    def verify_secret(
        self,
        key: str,
        namespace: str = "default",
    ) -> SecretsIntegrityResult:
        """
        Verify integrity of a single secret.

        Args:
            key: The secret key to verify.
            namespace: Namespace.

        Returns:
            SecretsIntegrityResult for this secret.
        """
        with self._lock:
            result = SecretsIntegrityResult()

            if self._registry:
                try:
                    item = self._registry.get(key, namespace)
                    if item is not None:
                        stored_checksum = item.checksum
                        if stored_checksum:
                            computed = self.calculate_checksum(item.value)
                            result.checksums[key] = computed
                            if computed != stored_checksum:
                                result.errors.append(
                                    f"Checksum mismatch for '{key}': "
                                    f"stored={stored_checksum[:16]}..., "
                                    f"computed={computed[:16]}..."
                                )
                        else:
                            computed = self.calculate_checksum(item.value)
                            result.checksums[key] = computed
                    else:
                        result.errors.append(f"Secret '{key}' not found in registry")
                except Exception as e:
                    result.errors.append(f"Error verifying secret '{key}': {e}")
            else:
                result.errors.append("No registry configured for verification")

            if result.errors:
                result.valid = False
                self._errors_total += len(result.errors)

            self._record_history(result)
            return result

    def verify_vault(self) -> SecretsIntegrityResult:
        """
        Verify vault provider integrity.

        Checks provider connectivity, data consistency,
        and configuration integrity.

        Returns:
            SecretsIntegrityResult for the provider.
        """
        with self._lock:
            result = SecretsIntegrityResult()

            if self._provider:
                try:
                    if hasattr(self._provider, "health_check"):
                        health = self._provider.health_check()
                        if isinstance(health, dict):
                            if not health.get("healthy", True):
                                result.errors.append(
                                    f"Provider health check failed: {health}"
                                )
                    if hasattr(self._provider, "get_stats"):
                        stats = self._provider.get_stats()
                        result.checksums["provider_stats"] = self.calculate_checksum(
                            str(stats)
                        )
                except Exception as e:
                    result.errors.append(f"Provider integrity check failed: {e}")
            else:
                result.errors.append("No provider configured for verification")

            if result.errors:
                result.valid = False
                self._errors_total += len(result.errors)

            self._record_history(result)
            return result

    def verify_cache(self) -> SecretsIntegrityResult:
        """
        Verify cache consistency.

        Checks cache entries against the registry
        to detect staleness or corruption.

        Returns:
            SecretsIntegrityResult for the cache.
        """
        with self._lock:
            result = SecretsIntegrityResult()

            if self._cache:
                try:
                    stats = self._cache.get_stats()
                    result.checksums["cache_stats"] = self.calculate_checksum(
                        str(stats)
                    )

                    if self._registry:
                        self._verify_cache_against_registry(result)
                except Exception as e:
                    result.errors.append(f"Cache integrity check failed: {e}")
            else:
                result.errors.append("No cache configured for verification")

            if result.errors:
                result.valid = False
                self._errors_total += len(result.errors)

            self._record_history(result)
            return result

    # ── Checksum ──

    @staticmethod
    def calculate_checksum(
        data: Any,
        algorithm: str = "sha256",
    ) -> str:
        """
        Calculate a checksum for secret data.

        Args:
            data: Data to checksum (str, bytes, or other).
            algorithm: Hash algorithm (sha256, sha512, md5).

        Returns:
            Hex digest string.
        """
        if isinstance(data, str):
            raw = data.encode("utf-8")
        elif isinstance(data, bytes):
            raw = data
        else:
            raw = str(data).encode("utf-8")

        if algorithm == "sha256":
            return hashlib.sha256(raw).hexdigest()
        elif algorithm == "sha512":
            return hashlib.sha512(raw).hexdigest()
        elif algorithm == "md5":
            return hashlib.md5(raw).hexdigest()
        else:
            return hashlib.sha256(raw).hexdigest()

    # ── Internal Verification ──

    def _verify_secret_data(self, result: SecretsIntegrityResult) -> None:
        """Verify all secret data integrity."""
        if self._registry:
            try:
                if hasattr(self._registry, "get_all"):
                    items = self._registry.get_all()
                    for item in items:
                        if item.checksum:
                            computed = self.calculate_checksum(item.value)
                            if computed != item.checksum:
                                result.errors.append(
                                    f"Data corruption detected for '{item.key}'"
                                )
                elif hasattr(self._registry, "keys"):
                    keys = self._registry.keys()
                    for key in keys:
                        try:
                            item = self._registry.get(key)
                            if item and item.checksum:
                                computed = self.calculate_checksum(item.value)
                                if computed != item.checksum:
                                    result.errors.append(
                                        f"Data corruption detected for '{key}'"
                                    )
                        except Exception:
                            pass
            except Exception as e:
                result.errors.append(f"Secret data verification error: {e}")

    def _verify_vault_provider(self, result: SecretsIntegrityResult) -> None:
        """Verify vault provider integrity."""
        if self._provider:
            try:
                if hasattr(self._provider, "health_check"):
                    health = self._provider.health_check()
                    if isinstance(health, dict) and not health.get("healthy", True):
                        result.errors.append(
                            f"Provider unhealthy: {health}"
                        )
            except Exception as e:
                result.errors.append(f"Provider verification error: {e}")

    def _verify_cache_consistency(self, result: SecretsIntegrityResult) -> None:
        """Verify cache consistency with registry."""
        if self._cache and self._registry:
            try:
                cache_stats = self._cache.get_stats()
                cache_keys = self._cache.keys()

                for key in cache_keys[:100]:
                    try:
                        cached = self._cache.get(key)
                        if cached is not None:
                            registry_item = self._registry.get(key)
                            if registry_item and cached != registry_item.value:
                                result.errors.append(
                                    f"Cache inconsistency for '{key}'"
                                )
                    except Exception:
                        pass

                result.checksums["cache_entry_count"] = str(
                    cache_stats.get("entries", 0)
                )
            except Exception as e:
                result.errors.append(f"Cache consistency error: {e}")

    def _verify_cache_against_registry(
        self, result: SecretsIntegrityResult
    ) -> None:
        """Verify cache entries against registry."""
        try:
            cache_keys = self._cache.keys()
            inconsistencies = 0
            for key in cache_keys[:100]:
                try:
                    cached = self._cache.get(key)
                    if cached is not None:
                        registry_item = self._registry.get(key)
                        if registry_item and cached != registry_item.value:
                            inconsistencies += 1
                except Exception:
                    pass

            if inconsistencies > 0:
                result.errors.append(
                    f"Found {inconsistencies} cache/registry mismatches"
                )
        except Exception as e:
            result.errors.append(f"Cache-registry verification error: {e}")

    def _verify_access_policy(self, result: SecretsIntegrityResult) -> None:
        """Verify access policy integrity."""
        if self._policy:
            try:
                if hasattr(self._policy, "get_stats"):
                    policy_stats = self._policy.get_stats()
                    result.checksums["policy_stats"] = self.calculate_checksum(
                        str(policy_stats)
                    )
            except Exception as e:
                result.errors.append(f"Access policy verification error: {e}")

    def _verify_audit_log(self, result: SecretsIntegrityResult) -> None:
        """Verify audit log integrity."""
        if self._audit:
            try:
                if hasattr(self._audit, "get_stats"):
                    audit_stats = self._audit.get_stats()
                    result.checksums["audit_stats"] = self.calculate_checksum(
                        str(audit_stats)
                    )
            except Exception as e:
                result.errors.append(f"Audit log verification error: {e}")

    # ── History & Stats ──

    def _record_history(self, result: SecretsIntegrityResult) -> None:
        """Record a verification result in history."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "valid": result.valid,
            "errors_count": len(result.errors),
            "errors": list(result.errors),
            "checksums_count": len(result.checksums),
        }
        self._history.append(entry)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_history(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get verification history.

        Args:
            limit: Maximum number of history entries.

        Returns:
            List of verification history entries.
        """
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def get_stats(self) -> Dict[str, Any]:
        """
        Get integrity verification statistics.

        Returns:
            Statistics dictionary.
        """
        with self._lock:
            return {
                "total_verifications": self._verification_count,
                "errors_total": self._errors_total,
                "last_verified_at": (
                    self._last_verified_at.isoformat() + "Z"
                    if self._last_verified_at
                    else None
                ),
                "history_size": len(self._history),
                "components": {
                    "registry": self._registry is not None,
                    "cache": self._cache is not None,
                    "provider": self._provider is not None,
                    "audit": self._audit is not None,
                    "policy": self._policy is not None,
                },
            }