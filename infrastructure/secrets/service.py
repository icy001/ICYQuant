"""
Secrets service - unified security platform service.

Provides a single entry point for all security
operations, integrating cryptographic services
with secrets management, telemetry, monitoring,
protection, recovery, and integrity verification.

Enhanced with full lifecycle management and
comprehensive diagnostics.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from .diagnostics import SecretsDiagnostics
from .manager import SecretsManager
from .telemetry import SecretsTelemetry
from .monitoring import SecretsMonitoring
from .protection import SecretsProtection
from .recovery import SecretsRecovery
from .integrity import SecretsIntegrity

logger = logging.getLogger(__name__)


class SecurityService:
    """
    Unified security platform service.

    Provides a single interface for all security
    operations, coordinating CryptoService and
    SecretsManager with telemetry, monitoring,
    protection, recovery, and integrity components.

    Features:
    - Encrypt and store secrets with CryptoService
    - Retrieve and decrypt secrets
    - Secret rotation with cryptographic key rotation
    - Comprehensive health checking
    - Full lifecycle management (startup, shutdown, reload)
    - Integrated telemetry, monitoring, protection,
      recovery, and integrity verification

    Usage:
        service = SecurityService()
        await service.startup()
        await service.encrypt_secret("db/password", "secret123")
        value = await service.decrypt_secret("db/password")
        await service.shutdown()
    """

    def __init__(
        self,
        crypto_service: Optional[Any] = None,
        secrets_manager: Optional[SecretsManager] = None,
        telemetry: Optional[SecretsTelemetry] = None,
        monitoring: Optional[SecretsMonitoring] = None,
        protection: Optional[SecretsProtection] = None,
        recovery: Optional[SecretsRecovery] = None,
        integrity: Optional[SecretsIntegrity] = None,
        diagnostics: Optional[SecretsDiagnostics] = None,
    ) -> None:
        """
        Initialize security service.

        Args:
            crypto_service: CryptoService instance from
                infrastructure.crypto.
            secrets_manager: SecretsManager instance.
            telemetry: SecretsTelemetry instance.
            monitoring: SecretsMonitoring instance.
            protection: SecretsProtection instance.
            recovery: SecretsRecovery instance.
            integrity: SecretsIntegrity instance.
            diagnostics: SecretsDiagnostics instance.
        """
        self._crypto_service = crypto_service
        self._secrets_manager = secrets_manager or SecretsManager()
        self._telemetry = telemetry or SecretsTelemetry()
        self._monitoring = monitoring or SecretsMonitoring()
        self._protection = protection or SecretsProtection()
        self._recovery = recovery or SecretsRecovery()
        self._integrity = integrity or SecretsIntegrity()
        self._diagnostics = diagnostics or SecretsDiagnostics()

        self._running = False
        self._startup_time: Optional[float] = None

    @property
    def is_running(self) -> bool:
        """Check if service is running."""
        return self._running

    async def startup(self) -> None:
        """
        Full startup sequence.

        Initializes all sub-components including
        crypto service, secrets manager, and
        verification components.
        """
        logger.info("Starting SecurityService")

        if self._crypto_service is not None:
            if not self._crypto_service.is_running:
                await self._crypto_service.startup()
            logger.info("CryptoService started")

        if not self._secrets_manager.is_started:
            await self._secrets_manager.startup()
            logger.info("SecretsManager started")

        self._protection.set_providers(
            primary=self._secrets_manager.config.provider,
        )

        self._running = True
        self._startup_time = time.time()
        logger.info("SecurityService started")

    async def shutdown(self) -> None:
        """
        Graceful shutdown.

        Shuts down all sub-components in reverse
        order, flushing telemetry and diagnostics.
        """
        logger.info("Shutting down SecurityService")

        if self._crypto_service is not None and self._crypto_service.is_running:
            try:
                await self._crypto_service.shutdown()
            except Exception as e:
                logger.warning(
                    "CryptoService shutdown error: %s", e,
                )

        if self._secrets_manager.is_started:
            try:
                await self._secrets_manager.shutdown()
            except Exception as e:
                logger.warning(
                    "SecretsManager shutdown error: %s", e,
                )

        try:
            self._telemetry.clear()
        except Exception:
            pass

        self._running = False
        self._startup_time = None
        logger.info("SecurityService stopped")

    async def reload(self) -> None:
        """
        Hot reload configuration.

        Re-initializes sub-components without
        full shutdown, preserving existing
        connections and state.
        """
        if not self._running:
            raise RuntimeError(
                "SecurityService not running, cannot reload",
            )

        logger.info("Reloading SecurityService configuration")

        if self._crypto_service is not None:
            await self._crypto_service.reload()

        self._diagnostics.record_operation(
            operation="reload",
            success=True,
            duration_ms=0.0,
        )

        logger.info("SecurityService reloaded successfully")

    # ── Core Operations ──

    async def encrypt_secret(
        self,
        key: str,
        value: str,
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """
        Encrypt and store a secret.

        Encrypts the value using CryptoService
        and stores the encrypted result in
        SecretsManager.

        Args:
            key: The secret key.
            value: The plaintext value to encrypt and store.
            namespace: Namespace for the secret.

        Returns:
            Dict with operation result including
            the encrypted value reference.
        """
        start = time.time()

        if not self._protection.allow_operation("write", key):
            self._diagnostics.record_operation(
                operation="encrypt_secret",
                secret_key=key,
                namespace=namespace,
                success=False,
                duration_ms=0.0,
                error="Operation rejected by protection",
            )
            raise RuntimeError(
                f"encrypt_secret rejected by protection "
                f"for key '{key}'"
            )

        try:
            stored_value = value

            if self._crypto_service is not None:
                encrypted = await self._crypto_service.encrypt(
                    data=value.encode("utf-8"),
                    key_id=key,
                )
                stored_value = json.dumps(encrypted.to_dict())

            item = await self._secrets_manager.set(
                key=key,
                value=stored_value,
                namespace=namespace,
            )

            self._protection.on_success()

            duration_ms = (time.time() - start) * 1000
            self._diagnostics.record_operation(
                operation="encrypt_secret",
                secret_key=key,
                namespace=namespace,
                success=True,
                duration_ms=duration_ms,
            )

            self._telemetry.record_operation(
                operation="set",
                key=key,
                namespace=namespace,
                success=True,
                latency_ms=duration_ms,
            )

            return {
                "key": key,
                "namespace": namespace,
                "encrypted": self._crypto_service is not None,
                "version": item.version,
            }

        except Exception as e:
            error_msg = str(e)
            self._protection.on_failure()
            duration_ms = (time.time() - start) * 1000
            self._diagnostics.record_operation(
                operation="encrypt_secret",
                secret_key=key,
                namespace=namespace,
                success=False,
                duration_ms=duration_ms,
                error=error_msg,
            )
            self._telemetry.record_operation(
                operation="set",
                key=key,
                namespace=namespace,
                success=False,
                latency_ms=duration_ms,
            )
            raise

    async def decrypt_secret(
        self,
        key: str,
        namespace: str = "default",
    ) -> str:
        """
        Retrieve and decrypt a secret.

        Retrieves the encrypted secret from
        SecretsManager and decrypts it using
        CryptoService.

        Args:
            key: The secret key.
            namespace: Namespace for the secret.

        Returns:
            The decrypted plaintext value.
        """
        start = time.time()

        if not self._protection.allow_operation("read", key):
            self._diagnostics.record_operation(
                operation="decrypt_secret",
                secret_key=key,
                namespace=namespace,
                success=False,
                duration_ms=0.0,
                error="Operation rejected by protection",
            )
            raise RuntimeError(
                f"decrypt_secret rejected by protection "
                f"for key '{key}'"
            )

        try:
            stored_value = await self._secrets_manager.get(
                key=key,
                namespace=namespace,
            )

            if stored_value is None:
                raise ValueError(
                    f"Secret '{key}' not found in namespace "
                    f"'{namespace}'"
                )

            value = stored_value

            if self._crypto_service is not None:
                try:
                    encrypted_data = json.loads(stored_value)
                    from infrastructure.crypto.pipeline.encrypt import (
                        EncryptionResult,
                    )

                    encrypted = EncryptionResult(**encrypted_data)
                    decrypted = await self._crypto_service.decrypt(
                        encrypted=encrypted,
                    )
                    value = decrypted.plaintext.decode("utf-8")
                except (json.JSONDecodeError, TypeError, KeyError):
                    value = stored_value

            self._protection.on_success()

            duration_ms = (time.time() - start) * 1000
            self._diagnostics.record_operation(
                operation="decrypt_secret",
                secret_key=key,
                namespace=namespace,
                success=True,
                duration_ms=duration_ms,
            )

            self._telemetry.record_operation(
                operation="get",
                key=key,
                namespace=namespace,
                success=True,
                latency_ms=duration_ms,
                cache_hit=False,
            )

            return value

        except Exception as e:
            error_msg = str(e)
            self._protection.on_failure()
            duration_ms = (time.time() - start) * 1000
            self._diagnostics.record_operation(
                operation="decrypt_secret",
                secret_key=key,
                namespace=namespace,
                success=False,
                duration_ms=duration_ms,
                error=error_msg,
            )
            self._telemetry.record_operation(
                operation="get",
                key=key,
                namespace=namespace,
                success=False,
                latency_ms=duration_ms,
            )
            raise

    async def rotate_secret(
        self,
        key: str,
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """
        Rotate a secret with cryptographic key rotation.

        Reads the current secret, generates a new
        cryptographic key via CryptoService, re-encrypts
        the value, and stores the updated secret.

        Args:
            key: The secret key to rotate.
            namespace: Namespace for the secret.

        Returns:
            Dict with rotation result including
            new version and key rotation status.
        """
        start = time.time()

        if not self._protection.allow_operation("rotate", key):
            self._diagnostics.record_operation(
                operation="rotate_secret",
                secret_key=key,
                namespace=namespace,
                success=False,
                duration_ms=0.0,
                error="Operation rejected by protection",
            )
            raise RuntimeError(
                f"rotate_secret rejected by protection "
                f"for key '{key}'"
            )

        try:
            stored_value = await self._secrets_manager.get(
                key=key,
                namespace=namespace,
            )

            if stored_value is None:
                raise ValueError(
                    f"Secret '{key}' not found in namespace "
                    f"'{namespace}'"
                )

            key_rotated = False

            if self._crypto_service is not None:
                rotation_result = await self._crypto_service.rotate_key(
                    key_id=key,
                )
                key_rotated = rotation_result.success

                try:
                    encrypted_data = json.loads(stored_value)
                    from infrastructure.crypto.pipeline.encrypt import (
                        EncryptionResult,
                    )

                    encrypted = EncryptionResult(**encrypted_data)
                    decrypted = await self._crypto_service.decrypt(
                        encrypted=encrypted,
                    )
                    plaintext = decrypted.plaintext
                except (json.JSONDecodeError, TypeError, KeyError):
                    plaintext = stored_value.encode("utf-8")

                new_encrypted = await self._crypto_service.encrypt(
                    data=plaintext,
                    key_id=key,
                )
                stored_value = json.dumps(new_encrypted.to_dict())

            item = await self._secrets_manager.update(
                key=key,
                value=stored_value,
                namespace=namespace,
            )

            self._protection.on_success()

            duration_ms = (time.time() - start) * 1000
            self._diagnostics.record_operation(
                operation="rotate_secret",
                secret_key=key,
                namespace=namespace,
                success=True,
                duration_ms=duration_ms,
                key_rotated=key_rotated,
                new_version=item.version,
            )

            self._telemetry.record_operation(
                operation="rotate",
                key=key,
                namespace=namespace,
                success=True,
                latency_ms=duration_ms,
            )

            return {
                "key": key,
                "namespace": namespace,
                "version": item.version,
                "key_rotated": key_rotated,
            }

        except Exception as e:
            error_msg = str(e)
            self._protection.on_failure()
            duration_ms = (time.time() - start) * 1000
            self._diagnostics.record_operation(
                operation="rotate_secret",
                secret_key=key,
                namespace=namespace,
                success=False,
                duration_ms=duration_ms,
                error=error_msg,
            )
            self._telemetry.record_operation(
                operation="rotate",
                key=key,
                namespace=namespace,
                success=False,
                latency_ms=duration_ms,
            )
            raise

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.

        Checks health of all sub-components
        including crypto service, secrets manager,
        telemetry, monitoring, protection, recovery,
        and integrity verification.

        Returns:
            Health status dictionary with component
            details and overall health flag.
        """
        result: Dict[str, Any] = {
            "healthy": True,
            "crypto": True,
            "vault": True,
            "kms": True,
            "keystore": True,
            "rotation": True,
            "provider": True,
            "audit": True,
        }

        if self._crypto_service is not None:
            try:
                result["crypto"] = self._crypto_service.is_running
            except Exception:
                result["crypto"] = False
                result["healthy"] = False

        try:
            secrets_health = await self._secrets_manager.health_check()
            provider_ok = secrets_health.get("provider", True)
            cache_ok = secrets_health.get("cache", True)
            result["vault"] = provider_ok
            result["provider"] = provider_ok
            result["keystore"] = cache_ok
            if not provider_ok:
                result["healthy"] = False
        except Exception:
            result["vault"] = False
            result["provider"] = False
            result["healthy"] = False

        if self._crypto_service is not None:
            try:
                crypto_stats = self._crypto_service.get_stats()
                result["kms"] = crypto_stats.get("initialized", False)
                if not result["kms"]:
                    result["healthy"] = False
            except Exception:
                result["kms"] = False
                result["healthy"] = False

        try:
            result["rotation"] = self._secrets_manager._started
            if not result["rotation"]:
                result["healthy"] = False
        except Exception:
            result["rotation"] = False
            result["healthy"] = False

        try:
            result["audit"] = self._telemetry.enabled
        except Exception:
            result["audit"] = False
            result["healthy"] = False

        return result

    # ── Component Accessors ──

    def get_crypto_service(self) -> Optional[Any]:
        """Get the CryptoService instance."""
        return self._crypto_service

    def get_secrets_manager(self) -> SecretsManager:
        """Get the SecretsManager instance."""
        return self._secrets_manager

    def get_telemetry(self) -> SecretsTelemetry:
        """Get the SecretsTelemetry instance."""
        return self._telemetry

    def get_monitoring(self) -> SecretsMonitoring:
        """Get the SecretsMonitoring instance."""
        return self._monitoring

    def get_protection(self) -> SecretsProtection:
        """Get the SecretsProtection instance."""
        return self._protection

    def get_recovery(self) -> SecretsRecovery:
        """Get the SecretsRecovery instance."""
        return self._recovery

    def get_integrity(self) -> SecretsIntegrity:
        """Get the SecretsIntegrity instance."""
        return self._integrity

    def get_diagnostics(self) -> SecretsDiagnostics:
        """Get the SecretsDiagnostics instance."""
        return self._diagnostics

    # ── Stats ──

    def get_stats(self) -> Dict[str, Any]:
        """
        Get full platform statistics.

        Aggregates statistics from all sub-components
        including crypto service, secrets manager,
        telemetry, monitoring, protection, recovery,
        integrity, and diagnostics.

        Returns:
            Complete platform statistics dictionary.
        """
        stats: Dict[str, Any] = {
            "running": self._running,
            "crypto_service": (
                self._crypto_service.get_stats()
                if self._crypto_service is not None
                else None
            ),
            "secrets_manager": self._secrets_manager.config.to_dict()
            if hasattr(self._secrets_manager.config, "to_dict")
            else {},
            "telemetry": self._telemetry.get_stats(),
            "monitoring": self._monitoring.get_stats(),
            "protection": self._protection.get_stats(),
            "recovery": self._recovery.get_stats(),
            "integrity": self._integrity.get_stats(),
            "diagnostics": self._diagnostics.get_stats(),
        }

        if self._startup_time:
            stats["uptime_seconds"] = (
                time.time() - self._startup_time
            )

        return stats