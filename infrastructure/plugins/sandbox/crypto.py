"""Cryptographic providers for sandbox security.

Provides :class:`CryptoProvider` for encryption/decryption,
:class:`SignatureVerifier` for plugin signature verification,
and :class:`TrustStore` for managing trusted plugin identities.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

from ..exceptions import PluginSignatureError, PluginTrustError

logger = logging.getLogger(__name__)


class CryptoProvider:
    """Provides encryption and hashing utilities for sandbox security.

    Supports AES-256-GCM-style encryption using ``cryptography``
    (when available) with a fallback to XOR-based obfuscation for
    environments where the ``cryptography`` package is not
    installed.  **The fallback is NOT secure** and should only
    be used for development/testing.

    Attributes:
        _key: The encryption key derived from the provided secret.
        _use_cryptography: Whether the ``cryptography`` package is
            available for secure encryption.
    """

    def __init__(self, secret: Optional[bytes] = None) -> None:
        """Initialize the crypto provider.

        Args:
            secret: Optional secret for key derivation. If not
                provided, a random key is generated.
        """
        self._lock = threading.RLock()
        self._use_cryptography = False
        self._cipher = None

        try:
            from cryptography.hazmat.primitives.ciphers.aead import (
                AESGCM,
            )

            self._use_cryptography = True
            key = secret or os.urandom(32)
            self._cipher = AESGCM(key)
            logger.info("CryptoProvider initialized with AES-GCM")
        except ImportError:
            key = secret or os.urandom(32)
            self._key = key
            logger.warning(
                "cryptography package not available; using fallback "
                "XOR encryption (NOT secure for production)"
            )

    def encrypt(self, data: bytes, associated_data: bytes = b"") -> bytes:
        """Encrypt data.

        Args:
            data: The plaintext bytes to encrypt.
            associated_data: Additional authenticated data (AAD).

        Returns:
            The encrypted ciphertext with nonce prepended.
        """
        with self._lock:
            if self._use_cryptography and self._cipher is not None:
                nonce = os.urandom(12)
                ct = self._cipher.encrypt(nonce, data, associated_data)
                return nonce + ct
            return self._fallback_encrypt(data)

    def decrypt(
        self, token: bytes, associated_data: bytes = b""
    ) -> bytes:
        """Decrypt data.

        Args:
            token: The ciphertext with nonce prepended.
            associated_data: Additional authenticated data (AAD).

        Returns:
            The decrypted plaintext bytes.

        Raises:
            PluginSecurityError: If decryption fails.
        """
        with self._lock:
            if self._use_cryptography and self._cipher is not None:
                nonce = token[:12]
                ct = token[12:]
                try:
                    return self._cipher.decrypt(nonce, ct, associated_data)
                except Exception as exc:
                    from ..exceptions import PluginSecurityError

                    raise PluginSecurityError(
                        "Decryption failed: invalid or tampered data"
                    ) from exc
            return self._fallback_decrypt(token)

    def _fallback_encrypt(self, data: bytes) -> bytes:
        """Fallback XOR encryption (NOT secure)."""
        key = self._key
        nonce = os.urandom(8)
        key_stream = hashlib.sha256(
            nonce + key
        ).digest() * (len(data) // 32 + 1)
        encrypted = bytes(
            d ^ k for d, k in zip(data, key_stream[: len(data)])
        )
        return nonce + encrypted

    def _fallback_decrypt(self, token: bytes) -> bytes:
        """Fallback XOR decryption (NOT secure)."""
        key = self._key
        nonce = token[:8]
        data = token[8:]
        key_stream = hashlib.sha256(
            nonce + key
        ).digest() * (len(data) // 32 + 1)
        return bytes(
            d ^ k for d, k in zip(data, key_stream[: len(data)])
        )

    @staticmethod
    def hash_data(
        data: bytes, algorithm: str = "sha256"
    ) -> str:
        """Compute a hex digest of data.

        Args:
            data: The bytes to hash.
            algorithm: Hash algorithm name (``sha256``, ``sha512``, etc.).

        Returns:
            The hex-encoded digest string.
        """
        h = hashlib.new(algorithm)
        h.update(data)
        return h.hexdigest()

    def get_stats(self) -> Dict[str, Any]:
        """Get crypto provider statistics.

        Returns:
            A dictionary with encryption mode info.
        """
        return {
            "use_cryptography": self._use_cryptography,
            "algorithm": "AES-256-GCM"
            if self._use_cryptography
            else "XOR-fallback",
        }


class SignatureVerifier:
    """Verifies plugin signatures to ensure authenticity and integrity.

    Supports HMAC-SHA256 based signature verification.

    Attributes:
        _public_keys: Maps plugin_id to its public key bytes.
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self) -> None:
        self._public_keys: Dict[str, bytes] = {}
        self._lock = threading.RLock()

    def register_key(
        self, plugin_id: str, public_key: bytes
    ) -> None:
        """Register a public key for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            public_key: The public key bytes.
        """
        with self._lock:
            self._public_keys[plugin_id] = public_key
            logger.debug(
                "Registered public key for plugin %s", plugin_id
            )

    def verify(
        self,
        plugin_id: str,
        data: bytes,
        signature: bytes,
    ) -> bool:
        """Verify a plugin's signature.

        Args:
            plugin_id: Unique identifier for the plugin.
            data: The original signed data.
            signature: The HMAC signature bytes.

        Returns:
            True if the signature is valid, False otherwise.
        """
        with self._lock:
            key = self._public_keys.get(plugin_id)
            if key is None:
                logger.warning(
                    "No public key registered for plugin %s", plugin_id
                )
                return False
            expected = hmac.new(key, data, hashlib.sha256).digest()
            return hmac.compare_digest(expected, signature)

    def require_verification(
        self,
        plugin_id: str,
        data: bytes,
        signature: bytes,
    ) -> None:
        """Require valid signature, raising if invalid.

        Args:
            plugin_id: Unique identifier for the plugin.
            data: The original signed data.
            signature: The HMAC signature bytes.

        Raises:
            PluginSignatureError: If the signature is invalid or
                no key is registered.
        """
        if not self.verify(plugin_id, data, signature):
            raise PluginSignatureError(
                f"Signature verification failed for plugin: {plugin_id}"
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get signature verifier statistics.

        Returns:
            A dictionary with registered key count.
        """
        with self._lock:
            return {
                "registered_keys": len(self._public_keys),
                "plugins": sorted(self._public_keys.keys()),
            }


class TrustStore:
    """Manages trusted plugin identities.

    Plugins must be registered in the trust store before they
    can be loaded and executed in a sandbox.

    Attributes:
        _trusted: Maps plugin_id to trust metadata.
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self) -> None:
        self._trusted: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def trust_plugin(
        self,
        plugin_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a plugin to the trust store.

        Args:
            plugin_id: Unique identifier for the plugin.
            metadata: Optional trust metadata (e.g. publisher,
                expiry).
        """
        with self._lock:
            self._trusted[plugin_id] = {
                "trusted_at": time.time(),
                "metadata": metadata or {},
            }
            logger.info("Added plugin %s to trust store", plugin_id)

    def distrust_plugin(self, plugin_id: str) -> None:
        """Remove a plugin from the trust store.

        Args:
            plugin_id: Unique identifier for the plugin.
        """
        with self._lock:
            self._trusted.pop(plugin_id, None)
            logger.info("Removed plugin %s from trust store", plugin_id)

    def is_trusted(self, plugin_id: str) -> bool:
        """Check whether a plugin is in the trust store.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            True if the plugin is trusted.
        """
        with self._lock:
            return plugin_id in self._trusted

    def require_trusted(self, plugin_id: str) -> None:
        """Require trust, raising if not trusted.

        Args:
            plugin_id: Unique identifier for the plugin.

        Raises:
            PluginTrustError: If the plugin is not in the trust store.
        """
        if not self.is_trusted(plugin_id):
            raise PluginTrustError(
                f"Plugin '{plugin_id}' is not in the trust store"
            )

    def get_trusted_plugins(self) -> List[str]:
        """Get the list of trusted plugin IDs.

        Returns:
            A sorted list of trusted plugin IDs.
        """
        with self._lock:
            return sorted(self._trusted.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Get trust store statistics.

        Returns:
            A dictionary with trusted plugin count.
        """
        with self._lock:
            return {
                "total_trusted": len(self._trusted),
                "plugins": sorted(self._trusted.keys()),
            }