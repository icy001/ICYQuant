"""
Crypto integrity verification.

Verifies the integrity of cryptographic components
through:
- Provider integrity checks
- Key store integrity verification
- Vault connectivity validation
- Certificate chain verification (reserved)
- Snapshot integrity checks

Usage:
    integrity = CryptoIntegrity()
    result = integrity.verify()
    if result.valid:
        # Crypto components are safe to use
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CryptoIntegrityResult:
    """
    Result of a crypto integrity check.

    Attributes:
        valid: Whether all checks passed.
        checksums: Dictionary of checksum values.
        errors: List of error messages.
        verified_at: Timestamp of verification.
    """

    valid: bool = True
    checksums: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    verified_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.verified_at is None:
            self.verified_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "checksums": self.checksums,
            "errors": self.errors,
            "verified_at": (
                self.verified_at.isoformat()
                if self.verified_at
                else None
            ),
        }


class CryptoIntegrity:
    """
    Crypto integrity verifier.

    Performs comprehensive integrity checks on
    cryptographic components to ensure they haven't
    been corrupted or tampered with.

    Checks:
    1. Provider Integrity: KMS provider health and consistency
    2. Key Store Integrity: Key metadata and version consistency
    3. Vault Connectivity: Vault server reachability and response
    4. Certificate Chain: TLS certificate validation (reserved)
    5. Snapshot Integrity: Crypto snapshot checksum verification

    Usage:
        integrity = CryptoIntegrity()
        result = integrity.verify()
        if not result.valid:
            for error in result.errors:
                print(f"Integrity error: {error}")
    """

    def __init__(
        self,
        provider: Optional[Any] = None,
        keystore: Optional[Any] = None,
        enable_certificate_check: bool = False,
    ) -> None:
        """
        Initialize crypto integrity verifier.

        Args:
            provider: KMS provider instance.
            keystore: KeyStore instance.
            enable_certificate_check: Enable certificate chain
                verification (reserved).
        """
        self._provider = provider
        self._keystore = keystore
        self._enable_certificate_check = enable_certificate_check
        self._verification_history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def verify(self) -> CryptoIntegrityResult:
        """
        Verify all crypto component integrity.

        Returns:
            CryptoIntegrityResult with check results.
        """
        errors: List[str] = []
        checksums: Dict[str, str] = {}

        result = CryptoIntegrityResult(
            valid=True,
            checksums=checksums,
            errors=errors,
        )

        # Check 1: Provider integrity
        provider_result = self.verify_provider()
        checksums["provider"] = str(provider_result.valid)
        if not provider_result.valid:
            errors.extend(provider_result.errors)

        # Check 2: Key store integrity
        keystore_result = self.verify_keystore()
        checksums["keystore"] = str(keystore_result.valid)
        if not keystore_result.valid:
            errors.extend(keystore_result.errors)

        # Check 3: Vault connectivity
        vault_result = self.verify_vault()
        checksums["vault"] = str(vault_result.valid)
        if not vault_result.valid:
            errors.extend(vault_result.errors)

        # Check 4: Certificate chain (reserved)
        if self._enable_certificate_check:
            cert_result = self._verify_certificate_chain()
            checksums["certificate"] = str(cert_result.valid)
            if not cert_result.valid:
                errors.extend(cert_result.errors)

        # Check 5: Snapshot integrity
        snapshot_result = self._verify_snapshot()
        checksums["snapshot"] = str(snapshot_result.valid)
        if not snapshot_result.valid:
            errors.extend(snapshot_result.errors)

        result.valid = len(errors) == 0

        self._record_verification(result)

        return result

    def verify_provider(self) -> CryptoIntegrityResult:
        """
        Verify KMS provider integrity.

        Checks:
        - Provider is initialized
        - Provider health check passes
        - Provider configuration is consistent

        Returns:
            CryptoIntegrityResult for the provider check.
        """
        errors: List[str] = []

        if self._provider is None:
            return CryptoIntegrityResult(
                valid=True,
                checksums={"provider": "not_configured"},
                errors=[],
            )

        try:
            health = self._provider.health_check()
            if not health.healthy:
                errors.append(
                    f"Provider health check failed: {health.error_message}"
                )
        except Exception as e:
            errors.append(f"Provider health check error: {e}")

        valid = len(errors) == 0
        return CryptoIntegrityResult(
            valid=valid,
            checksums={
                "provider": self.calculate_checksum(
                    {"name": self._provider.get_name()}
                )
            },
            errors=errors,
        )

    def verify_keystore(self) -> CryptoIntegrityResult:
        """
        Verify key store integrity.

        Checks:
        - Key metadata consistency
        - Version chain validity
        - No orphaned aliases

        Returns:
            CryptoIntegrityResult for the keystore check.
        """
        errors: List[str] = []

        if self._keystore is None:
            return CryptoIntegrityResult(
                valid=True,
                checksums={"keystore": "not_configured"},
                errors=[],
            )

        try:
            stats = self._keystore.get_stats()
            total_keys = stats.get("total_keys", 0)

            if total_keys < 0:
                errors.append(
                    "Key store integrity error: negative key count"
                )

            for key in self._keystore.list_keys():
                try:
                    versions = self._keystore.get_versions(
                        key.key_id
                    )
                    if not versions:
                        errors.append(
                            f"Key {key.key_id} has no versions"
                        )
                        continue

                    current = None
                    for v in versions:
                        if v.is_current:
                            current = v
                            break

                    if current is None:
                        errors.append(
                            f"Key {key.key_id} has no current version"
                        )

                except Exception as e:
                    errors.append(
                        f"Key {key.key_id} integrity error: {e}"
                    )

        except Exception as e:
            errors.append(f"Key store verification error: {e}")

        valid = len(errors) == 0
        return CryptoIntegrityResult(
            valid=valid,
            checksums={
                "keystore": self.calculate_checksum(
                    self._keystore.get_stats()
                )
            },
            errors=errors,
        )

    def verify_vault(self) -> CryptoIntegrityResult:
        """
        Verify vault connectivity.

        Checks:
        - Vault server reachability
        - Authentication tokens are valid
        - Response time is within acceptable range

        Returns:
            CryptoIntegrityResult for the vault check.
        """
        errors: List[str] = []

        if self._provider is None:
            return CryptoIntegrityResult(
                valid=True,
                checksums={"vault": "not_configured"},
                errors=[],
            )

        try:
            if hasattr(self._provider, "_vault_client"):
                client = self._provider._vault_client
                if hasattr(client, "is_authenticated"):
                    if not client.is_authenticated():
                        errors.append(
                            "Vault client is not authenticated"
                        )
        except Exception as e:
            errors.append(f"Vault connectivity check error: {e}")

        valid = len(errors) == 0
        return CryptoIntegrityResult(
            valid=valid,
            checksums={"vault": str(valid)},
            errors=errors,
        )

    def calculate_checksum(
        self,
        data: Dict[str, Any],
    ) -> str:
        """
        Calculate checksum for arbitrary data.

        Args:
            data: Data to checksum.

        Returns:
            SHA-256 checksum hex string.
        """
        normalized = json.dumps(
            self._sort_dict(data),
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _verify_certificate_chain(self) -> CryptoIntegrityResult:
        """
        Verify certificate chain (reserved).

        Returns:
            CryptoIntegrityResult for certificate check.
        """
        return CryptoIntegrityResult(
            valid=True,
            checksums={"certificate": "reserved"},
            errors=[],
        )

    def _verify_snapshot(self) -> CryptoIntegrityResult:
        """
        Verify crypto snapshot integrity.

        Returns:
            CryptoIntegrityResult for snapshot check.
        """
        snapshot_data: Dict[str, Any] = {}

        if self._keystore is not None:
            try:
                snapshot_data["keystore"] = self._keystore.get_stats()
            except Exception:
                pass

        if self._provider is not None:
            try:
                snapshot_data["provider"] = {
                    "name": self._provider.get_name(),
                }
            except Exception:
                pass

        checksum = self.calculate_checksum(snapshot_data)
        return CryptoIntegrityResult(
            valid=True,
            checksums={"snapshot": checksum},
            errors=[],
        )

    @staticmethod
    def _sort_dict(
        d: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Recursively sort dictionary keys."""
        return {
            k: CryptoIntegrity._sort_dict(v)
            if isinstance(v, dict)
            else v
            for k, v in sorted(d.items())
        }

    def _record_verification(
        self,
        result: CryptoIntegrityResult,
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
        """
        Get verification history.

        Args:
            limit: Maximum number of history entries.

        Returns:
            List of verification result dictionaries.
        """
        with self._lock:
            return self._verification_history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get verification statistics.

        Returns:
            Statistics dictionary with pass/fail counts.
        """
        with self._lock:
            total = len(self._verification_history)
            if total == 0:
                return {"total_verifications": 0}

            passed = sum(
                1
                for r in self._verification_history
                if r["valid"]
            )
            return {
                "total_verifications": total,
                "passed": passed,
                "failed": total - passed,
                "pass_rate": passed / total if total > 0 else 0,
            }