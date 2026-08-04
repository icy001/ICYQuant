"""
Crypto manager - high-level orchestrator.

Provides a simplified API for common
cryptographic operations, integrating
the CryptoService, KeyStore, and
Keyring into a unified interface.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .config import CryptoConfig
from .envelope import EnvelopeEncryption
from .keystore import KeyStore
from .keyring import Keyring
from .service import CryptoService
from .factory import CryptoFactory

logger = logging.getLogger(__name__)


class CryptoManager:
    """
    High-level crypto manager.

    Provides a simplified API for common
    cryptographic operations, integrating
    all crypto subsystems.

    Usage:
        manager = CryptoManager()
        await manager.initialize()

        encrypted = await manager.encrypt(
            data=b"secret",
            key_id="my-key",
        )
        decrypted = await manager.decrypt(encrypted)
    """

    def __init__(
        self,
        config: Optional[CryptoConfig] = None,
    ) -> None:
        """
        Initialize crypto manager.

        Args:
            config: Crypto configuration.
        """
        self._config = config or CryptoConfig()
        self._factory = CryptoFactory(self._config)
        self._service = CryptoService(self._config, self._factory)
        self._key_store = KeyStore()
        self._keyring = Keyring()
        self._envelope: Optional[EnvelopeEncryption] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all crypto subsystems."""
        await self._service.initialize()

        # Create envelope encryption handler
        if self._service._kms_provider:
            self._envelope = EnvelopeEncryption(
                registry=self._service._registry,
                kms_provider=self._service._kms_provider,
                config=self._config,
            )

        self._initialized = True
        logger.info("CryptoManager initialized")

    async def encrypt(
        self,
        data: bytes,
        key_id: str,
        algorithm_name: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Encrypt data.

        Args:
            data: Plaintext data.
            key_id: KMS key ID.
            algorithm_name: Algorithm override.

        Returns:
            Encrypted result.
        """
        self._check_initialized()
        return await self._service.encrypt(
            data=data,
            key_id=key_id,
            algorithm_name=algorithm_name,
            **kwargs,
        )

    async def decrypt(
        self,
        encrypted: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Decrypt data.

        Args:
            encrypted: Encrypted result.

        Returns:
            Decrypted result.
        """
        self._check_initialized()
        return await self._service.decrypt(encrypted, **kwargs)

    async def sign(
        self,
        data: bytes,
        private_key: Any,
        algorithm_name: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """Sign data."""
        self._check_initialized()
        return await self._service.sign(
            data=data,
            private_key=private_key,
            algorithm_name=algorithm_name,
            **kwargs,
        )

    async def verify(
        self,
        data: bytes,
        signature: str,
        public_key: Any,
        algorithm_name: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """Verify signature."""
        self._check_initialized()
        return await self._service.verify(
            data=data,
            signature=signature,
            public_key=public_key,
            algorithm_name=algorithm_name,
            **kwargs,
        )

    async def hash(
        self,
        data: bytes,
        algorithm_name: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """Hash data."""
        self._check_initialized()
        return await self._service.hash(
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
    ) -> Any:
        """Compute HMAC."""
        self._check_initialized()
        return await self._service.hmac(
            data=data,
            key=key,
            algorithm_name=algorithm_name,
            **kwargs,
        )

    async def rotate_key(
        self,
        key_id: str,
        **kwargs: Any,
    ) -> Any:
        """Rotate a cryptographic key."""
        self._check_initialized()
        return await self._service.rotate_key(key_id=key_id, **kwargs)

    def get_service(self) -> CryptoService:
        """Get underlying CryptoService."""
        return self._service

    def get_key_store(self) -> KeyStore:
        """Get key metadata store."""
        return self._key_store

    def get_keyring(self) -> Keyring:
        """Get key material store."""
        return self._keyring

    def get_envelope(self) -> Optional[EnvelopeEncryption]:
        """Get envelope encryption handler."""
        return self._envelope

    def get_config(self) -> CryptoConfig:
        """Get crypto configuration."""
        return self._config

    def _check_initialized(self) -> None:
        """Check if manager is initialized."""
        if not self._initialized:
            raise RuntimeError(
                "CryptoManager not initialized. Call initialize() first."
            )

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform crypto health check.

        Returns:
            Health status dictionary.
        """
        status = {
            "initialized": self._initialized,
            "crypto_service": self._initialized,
            "key_store": self._key_store.count() >= 0,
            "keyring": self._keyring.count() >= 0,
            "envelope": self._envelope is not None,
        }

        if self._service._kms_provider:
            try:
                kms_health = await self._service._kms_provider.health_check()
                status["kms"] = kms_health.to_dict()
            except Exception as e:
                status["kms"] = {"healthy": False, "error": str(e)}

        return {
            "healthy": all(
                v is True or (isinstance(v, dict) and v.get("healthy", False))
                for v in status.values()
            ),
            "components": status,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            "initialized": self._initialized,
            "service": self._service.get_stats(),
            "key_store": self._key_store.get_stats(),
            "keyring": self._keyring.get_stats(),
            "config": self._config.to_dict(),
        }
