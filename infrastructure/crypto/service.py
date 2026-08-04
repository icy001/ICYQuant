"""
Crypto service - unified cryptographic operations.

Provides a single entry point for all
cryptographic operations including
encryption, decryption, signing,
verification, hashing, and HMAC.

Enhanced with full lifecycle management,
telemetry integration, protection, and recovery.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, Optional

from .config import CryptoConfig
from .factory import CryptoFactory
from .pipeline.encrypt import EncryptionPipeline, EncryptionResult
from .pipeline.decrypt import DecryptionPipeline, DecryptionResult
from .pipeline.sign import SigningPipeline, SigningResult
from .pipeline.verify import VerificationPipeline, VerificationResult
from .pipeline.hash import HashPipeline, HashResult, HMACResult
from .pipeline.rotate import KeyRotationPipeline, KeyRotationResult
from .registry import AlgorithmRegistry
from .telemetry import CryptoTelemetry
from .protection import CryptoProtection
from .recovery import CryptoRecovery
from .integrity import CryptoIntegrity
from .exceptions import CryptoKMSError

logger = logging.getLogger(__name__)


class CryptoService:
    """
    Unified cryptographic service.

    Provides a single interface for all
    cryptographic operations, integrating
    algorithm selection, KMS providers,
    and pipeline orchestration.

    Features:
    - Encryption / Decryption with envelope support
    - Signing / Verification
    - Hashing / HMAC
    - Password hashing
    - Key rotation
    - Automatic algorithm selection
    - Full lifecycle management
    - Telemetry auto-instrumentation
    - Protection (rate limit + circuit breaker)
    - Recovery (automatic failover)

    Usage:
        service = CryptoService()
        await service.startup()
        encrypted = await service.encrypt(b"data", "key-id")
        decrypted = await service.decrypt(encrypted)
        await service.shutdown()
    """

    def __init__(
        self,
        config: Optional[CryptoConfig] = None,
        factory: Optional[CryptoFactory] = None,
        telemetry: Optional[CryptoTelemetry] = None,
        protection: Optional[CryptoProtection] = None,
        recovery: Optional[CryptoRecovery] = None,
        integrity: Optional[CryptoIntegrity] = None,
    ) -> None:
        """
        Initialize crypto service.

        Args:
            config: Crypto configuration.
            factory: Crypto factory instance.
            telemetry: Crypto telemetry instance.
            protection: Crypto protection instance.
            recovery: Crypto recovery instance.
            integrity: Crypto integrity instance.
        """
        self._config = config or CryptoConfig()
        self._factory = factory or CryptoFactory(self._config)
        self._registry = self._factory._registry
        self._kms_provider: Optional[Any] = None

        self._telemetry = telemetry or CryptoTelemetry()
        self._protection = protection or CryptoProtection(
            enable_failover=self._config.enable_kms_failover,
        )
        self._recovery = recovery or CryptoRecovery()
        self._integrity = integrity or CryptoIntegrity()

        self._running = False
        self._startup_time: Optional[float] = None

        self._encrypt_pipeline: Optional[EncryptionPipeline] = None
        self._decrypt_pipeline: Optional[DecryptionPipeline] = None
        self._sign_pipeline: Optional[SigningPipeline] = None
        self._verify_pipeline: Optional[VerificationPipeline] = None
        self._hash_pipeline: Optional[HashPipeline] = None
        self._rotate_pipeline: Optional[KeyRotationPipeline] = None

    @property
    def is_running(self) -> bool:
        """Check if service is running."""
        return self._running

    async def startup(self) -> None:
        """
        Full startup sequence.

        Calls initialize() and sets up
        integration components including
        integrity verification and
        provider registration for recovery.
        """
        await self.initialize()

        if self._kms_provider is not None:
            provider_name = (
                self._kms_provider.get_name()
                if hasattr(self._kms_provider, "get_name")
                else "default"
            )
            self._protection.register_providers(
                primary=provider_name,
            )
            self._recovery.register_provider(
                name=provider_name,
                provider=self._kms_provider,
                is_primary=True,
            )
            self._integrity = CryptoIntegrity(
                provider=self._kms_provider,
            )

        self._running = True
        self._startup_time = time.time()
        logger.info("CryptoService started")

    async def shutdown(self) -> None:
        """
        Graceful shutdown.

        Flushes telemetry, closes KMS provider,
        and resets protection/recovery state.
        """
        try:
            self._telemetry.clear_history()
        except Exception:
            pass

        if self._kms_provider is not None:
            try:
                if hasattr(self._kms_provider, "shutdown"):
                    result = self._kms_provider.shutdown()
                    if hasattr(result, "__await__"):
                        await result
            except Exception as e:
                logger.warning(
                    "KMS provider shutdown error: %s", e,
                )

        self._protection.reset()
        self._recovery.reset()

        self._running = False
        self._startup_time = None
        logger.info("CryptoService stopped")

    async def reload(self) -> None:
        """
        Hot reload configuration.

        Re-initializes pipelines without
        full shutdown, preserving the
        current KMS provider connection.
        """
        if not self._running:
            raise RuntimeError(
                "CryptoService not running, cannot reload",
            )

        logger.info("Reloading CryptoService configuration")

        self._encrypt_pipeline = None
        self._decrypt_pipeline = None
        self._sign_pipeline = None
        self._verify_pipeline = None
        self._hash_pipeline = None
        self._rotate_pipeline = None

        self._register_default_algorithms()

        if self._kms_provider is not None:
            self._encrypt_pipeline = EncryptionPipeline(
                registry=self._registry,
                kms_provider=self._kms_provider,
                envelope_enabled=self._config.envelope_enabled,
            )
            self._decrypt_pipeline = DecryptionPipeline(
                registry=self._registry,
                kms_provider=self._kms_provider,
            )
            self._sign_pipeline = SigningPipeline(
                registry=self._registry,
            )
            self._verify_pipeline = VerificationPipeline(
                registry=self._registry,
            )
            self._hash_pipeline = HashPipeline(
                registry=self._registry,
            )
            self._rotate_pipeline = KeyRotationPipeline(
                kms_provider=self._kms_provider,
                config=self._config,
            )

        self._telemetry.record_operation(
            operation="reload",
            success=True,
            duration_ms=0.0,
        )
        logger.info("CryptoService reloaded successfully")

    def get_telemetry(self) -> CryptoTelemetry:
        """Get telemetry component."""
        return self._telemetry

    def get_protection(self) -> CryptoProtection:
        """Get protection component."""
        return self._protection

    def get_recovery(self) -> CryptoRecovery:
        """Get recovery component."""
        return self._recovery

    def get_integrity(self) -> CryptoIntegrity:
        """Get integrity component."""
        return self._integrity

    async def initialize(self) -> None:
        """Initialize crypto service and KMS provider."""
        self._kms_provider = self._factory.create_kms_provider()
        await self._kms_provider.initialize()

        self._encrypt_pipeline = EncryptionPipeline(
            registry=self._registry,
            kms_provider=self._kms_provider,
            envelope_enabled=self._config.envelope_enabled,
        )
        self._decrypt_pipeline = DecryptionPipeline(
            registry=self._registry,
            kms_provider=self._kms_provider,
        )
        self._sign_pipeline = SigningPipeline(
            registry=self._registry,
        )
        self._verify_pipeline = VerificationPipeline(
            registry=self._registry,
        )
        self._hash_pipeline = HashPipeline(
            registry=self._registry,
        )
        self._rotate_pipeline = KeyRotationPipeline(
            kms_provider=self._kms_provider,
            config=self._config,
        )

        self._register_default_algorithms()

        logger.info("CryptoService initialized")

    def _register_default_algorithms(self) -> None:
        """Register default algorithm implementations."""
        try:
            from .algorithms import (
                AES256GCM,
                ChaCha20Poly1305,
                RSA2048,
                RSA4096,
                ECDSAP256,
                ECDSAP384,
                Ed25519,
                X25519,
                HMACSHA256,
                HMACSHA512,
                SHA256,
                SHA512,
                BcryptPassword,
            )

            algorithms = [
                AES256GCM(),
                ChaCha20Poly1305(),
                RSA2048(),
                RSA4096(),
                ECDSAP256(),
                ECDSAP384(),
                Ed25519(),
                X25519(),
                HMACSHA256(),
                HMACSHA512(),
                SHA256(),
                SHA512(),
                BcryptPassword(),
            ]

            for algo in algorithms:
                self._registry.register(algo)

            logger.info(
                "Registered %d algorithms", self._registry.count(),
            )
        except Exception as e:
            logger.warning("Algorithm registration failed: %s", e)

    async def _execute_operation(
        self,
        operation: str,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute an operation with telemetry, protection, and recovery.

        Wraps the operation with:
        1. Protection rate limit check
        2. Telemetry tracing
        3. Success/failure recording
        4. Recovery triggering on KMS failures

        Args:
            operation: Operation name for telemetry.
            func: Async callable to execute.
            *args: Positional arguments for func.
            **kwargs: Keyword arguments for func.

        Returns:
            Result from func.

        Raises:
            RuntimeError: If protection rejects the operation.
            Exception: Re-raises any exception from func.
        """
        if not self._protection.allow_operation():
            self._telemetry.record_operation(
                operation=operation,
                success=False,
                duration_ms=0.0,
                error="Rate limited or circuit open",
            )
            raise RuntimeError(
                f"Operation '{operation}' rejected by protection: "
                f"rate limit exceeded or circuit breaker open",
            )

        start = time.perf_counter()
        error_msg = ""

        try:
            result = await func(*args, **kwargs)
            return result
        except CryptoKMSError as e:
            error_msg = str(e)
            self._protection.on_failure([error_msg])
            self._recovery.trigger_recovery(
                error=error_msg,
            )
            raise
        except Exception as e:
            error_msg = str(e)
            self._protection.on_failure([error_msg])
            raise
        else:
            self._protection.on_success()
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            self._telemetry.record_operation(
                operation=operation,
                algorithm=str(kwargs.get("algorithm_name", "")),
                key_id=str(kwargs.get("key_id", "")),
                success=not error_msg,
                duration_ms=duration_ms,
                error=error_msg,
            )

    async def encrypt(
        self,
        data: bytes,
        key_id: str,
        algorithm_name: Optional[str] = None,
        aad: Optional[bytes] = None,
        **kwargs: Any,
    ) -> EncryptionResult:
        """
        Encrypt data.

        Args:
            data: Plaintext data.
            key_id: KMS key ID.
            algorithm_name: Algorithm override.
            aad: Additional authenticated data.

        Returns:
            EncryptionResult.
        """
        if self._encrypt_pipeline is None:
            raise RuntimeError("CryptoService not initialized")

        return await self._execute_operation(
            "encrypt",
            self._encrypt_pipeline.encrypt,
            data=data,
            key_id=key_id,
            algorithm_name=algorithm_name,
            aad=aad,
            **kwargs,
        )

    async def decrypt(
        self,
        encrypted: EncryptionResult,
        key: Optional[bytes] = None,
        **kwargs: Any,
    ) -> DecryptionResult:
        """
        Decrypt data.

        Args:
            encrypted: EncryptionResult to decrypt.
            key: Direct key (non-envelope mode).

        Returns:
            DecryptionResult with plaintext.
        """
        if self._decrypt_pipeline is None:
            raise RuntimeError("CryptoService not initialized")

        return await self._execute_operation(
            "decrypt",
            self._decrypt_pipeline.decrypt,
            encrypted,
            key=key,
            **kwargs,
        )

    async def sign(
        self,
        data: bytes,
        private_key: Any,
        algorithm_name: Optional[str] = None,
        key_id: str = "",
        **kwargs: Any,
    ) -> SigningResult:
        """
        Sign data.

        Args:
            data: Data to sign.
            private_key: Private key.
            algorithm_name: Algorithm override.
            key_id: Key identifier.

        Returns:
            SigningResult with signature.
        """
        if self._sign_pipeline is None:
            raise RuntimeError("CryptoService not initialized")

        return await self._execute_operation(
            "sign",
            self._sign_pipeline.sign,
            data=data,
            private_key=private_key,
            algorithm_name=algorithm_name,
            key_id=key_id,
            **kwargs,
        )

    async def verify(
        self,
        data: bytes,
        signature: str,
        public_key: Any,
        algorithm_name: Optional[str] = None,
        key_id: str = "",
        **kwargs: Any,
    ) -> VerificationResult:
        """
        Verify a signature.

        Args:
            data: Original data.
            signature: Base64 signature.
            public_key: Public key.
            algorithm_name: Algorithm override.
            key_id: Key identifier.

        Returns:
            VerificationResult with validity.
        """
        if self._verify_pipeline is None:
            raise RuntimeError("CryptoService not initialized")

        return await self._execute_operation(
            "verify",
            self._verify_pipeline.verify,
            data=data,
            signature=signature,
            public_key=public_key,
            algorithm_name=algorithm_name,
            key_id=key_id,
            **kwargs,
        )

    async def hash(
        self,
        data: bytes,
        algorithm_name: Optional[str] = None,
        **kwargs: Any,
    ) -> HashResult:
        """
        Compute hash of data.

        Args:
            data: Data to hash.
            algorithm_name: Hash algorithm.

        Returns:
            HashResult with digest.
        """
        if self._hash_pipeline is None:
            raise RuntimeError("CryptoService not initialized")

        return await self._execute_operation(
            "hash",
            self._hash_pipeline.hash,
            data=data,
            algorithm_name=algorithm_name,
            **kwargs,
        )

    async def hmac(
        self,
        data: bytes,
        key: bytes,
        algorithm_name: Optional[str] = None,
        **kwargs: Any,
    ) -> HMACResult:
        """
        Compute HMAC.

        Args:
            data: Data to authenticate.
            key: HMAC key.
            algorithm_name: HMAC algorithm.

        Returns:
            HMACResult with digest.
        """
        if self._hash_pipeline is None:
            raise RuntimeError("CryptoService not initialized")

        return await self._execute_operation(
            "hmac",
            self._hash_pipeline.hmac,
            data=data,
            key=key,
            algorithm_name=algorithm_name,
            **kwargs,
        )

    async def verify_hmac(
        self,
        data: bytes,
        key: bytes,
        expected_hmac: str,
        algorithm_name: Optional[str] = None,
        **kwargs: Any,
    ) -> bool:
        """Verify HMAC integrity."""
        if self._hash_pipeline is None:
            raise RuntimeError("CryptoService not initialized")

        return await self._execute_operation(
            "verify_hmac",
            self._hash_pipeline.verify_hmac,
            data=data,
            key=key,
            expected_hmac=expected_hmac,
            algorithm_name=algorithm_name,
            **kwargs,
        )

    async def hash_password(
        self,
        password: str,
        algorithm_name: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Hash a password."""
        if self._hash_pipeline is None:
            raise RuntimeError("CryptoService not initialized")

        return await self._execute_operation(
            "hash_password",
            self._hash_pipeline.hash_password,
            password=password,
            algorithm_name=algorithm_name,
            **kwargs,
        )

    async def verify_password(
        self,
        password: str,
        hash_value: str,
        algorithm_name: Optional[str] = None,
        **kwargs: Any,
    ) -> bool:
        """Verify a password."""
        if self._hash_pipeline is None:
            raise RuntimeError("CryptoService not initialized")

        return await self._execute_operation(
            "verify_password",
            self._hash_pipeline.verify_password,
            password=password,
            hash_value=hash_value,
            algorithm_name=algorithm_name,
            **kwargs,
        )

    async def rotate_key(
        self,
        key_id: str,
        re_encrypt_callback: Optional[Any] = None,
        **kwargs: Any,
    ) -> KeyRotationResult:
        """
        Rotate a cryptographic key.

        Args:
            key_id: Key to rotate.
            re_encrypt_callback: Data re-encryption callback.

        Returns:
            KeyRotationResult.
        """
        if self._rotate_pipeline is None:
            raise RuntimeError("CryptoService not initialized")

        return await self._execute_operation(
            "rotate_key",
            self._rotate_pipeline.rotate_key,
            key_id=key_id,
            re_encrypt_callback=re_encrypt_callback,
            **kwargs,
        )

    def get_config(self) -> CryptoConfig:
        """Get current crypto configuration."""
        return self._config

    def get_registry(self) -> AlgorithmRegistry:
        """Get algorithm registry."""
        return self._registry

    def get_kms_provider(self) -> Optional[Any]:
        """Get KMS provider."""
        return self._kms_provider

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        stats: Dict[str, Any] = {
            "algorithms": self._registry.get_stats(),
            "kms_provider": (
                self._kms_provider.get_name()
                if self._kms_provider
                else None
            ),
            "config": self._config.to_dict(),
            "initialized": self._encrypt_pipeline is not None,
            "running": self._running,
        }

        if self._startup_time:
            stats["uptime_seconds"] = (
                time.time() - self._startup_time
            )

        stats["telemetry"] = self._telemetry.get_stats()
        stats["protection"] = self._protection.get_stats()
        stats["recovery"] = self._recovery.get_stats()
        stats["integrity"] = self._integrity.get_stats()

        return stats