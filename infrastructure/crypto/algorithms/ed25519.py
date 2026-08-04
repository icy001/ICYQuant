"""
Ed25519 and X25519 algorithms.

Implements Ed25519 signing and X25519
key exchange using the cryptography
library, providing modern curve25519
cryptography with excellent security
properties.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from ..constants import AlgorithmName
from ..exceptions import (
    CryptoEncryptionError,
    CryptoSignatureError,
)
from ..registry import AsymmetricAlgorithm

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PrivateKey,
        X25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


class Ed25519(AsymmetricAlgorithm):
    """
    Ed25519 digital signature algorithm.

    Provides high-performance Ed25519
    signing with deterministic key
    generation and fast verification.

    Features:
    - 256-bit keys
    - Deterministic signatures
    - Fast verification
    - Collision-resistant
    """

    name: str = AlgorithmName.ED25519.value
    version: str = "1.0.0"

    def __init__(self) -> None:
        self._key_size = 32
        self._signature_size = 64

    async def generate_keypair(self) -> tuple:
        """Generate a new Ed25519 key pair."""
        if not _HAS_CRYPTO:
            raise CryptoSignatureError(
                operation="generate",
                reason="cryptography library not available",
            )

        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        return private_bytes, public_bytes

    async def encrypt(
        self,
        data: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """Ed25519 does not support encryption."""
        raise CryptoEncryptionError(
            algorithm=self.name,
            reason="Ed25519 is a signing-only algorithm",
        )

    async def decrypt(
        self,
        ciphertext: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """Ed25519 does not support decryption."""
        raise CryptoEncryptionError(
            algorithm=self.name,
            reason="Ed25519 is a signing-only algorithm",
        )

    async def sign(
        self,
        data: bytes,
        private_key: Any,
        **kwargs: Any,
    ) -> bytes:
        """
        Sign data with Ed25519.

        Args:
            data: Data to sign.
            private_key: Raw or PEM-encoded private key.
        """
        if not _HAS_CRYPTO:
            raise CryptoSignatureError(
                operation="sign",
                reason="cryptography library not available",
            )

        try:
            if isinstance(private_key, bytes):
                if len(private_key) == 32:
                    private_key = Ed25519PrivateKey.from_private_bytes(private_key)
                else:
                    private_key = serialization.load_pem_private_key(
                        private_key, password=None,
                    )

            signature = private_key.sign(data)
            return signature
        except Exception as e:
            raise CryptoSignatureError(
                operation="sign",
                reason=str(e),
            )

    async def verify(
        self,
        data: bytes,
        signature: bytes,
        public_key: Any,
        **kwargs: Any,
    ) -> bool:
        """
        Verify Ed25519 signature.

        Args:
            data: Original data.
            signature: 64-byte signature.
            public_key: Raw or PEM-encoded public key.
        """
        if not _HAS_CRYPTO:
            return False

        try:
            if isinstance(public_key, bytes):
                if len(public_key) == 32:
                    public_key = Ed25519PublicKey.from_public_bytes(public_key)
                else:
                    public_key = serialization.load_pem_public_key(public_key)

            public_key.verify(signature, data)
            return True
        except Exception:
            return False

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "key_size": self._key_size,
            "signature_size": self._signature_size,
        }


class X25519(AsymmetricAlgorithm):
    """
    X25519 key agreement protocol.

    Provides Diffie-Hellman key exchange
    using Curve25519, suitable for
    establishing shared secrets.
    """

    name: str = AlgorithmName.X25519.value
    version: str = "1.0.0"

    def __init__(self) -> None:
        self._key_size = 32

    async def generate_keypair(self) -> tuple:
        """Generate a new X25519 key pair."""
        if not _HAS_CRYPTO:
            raise CryptoEncryptionError(
                algorithm=self.name,
                reason="cryptography library not available",
            )

        private_key = X25519PrivateKey.generate()
        public_key = private_key.public_key()

        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        return private_bytes, public_bytes

    async def encrypt(
        self,
        data: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """X25519 does not support direct encryption."""
        raise CryptoEncryptionError(
            algorithm=self.name,
            reason="X25519 is a key exchange-only algorithm",
        )

    async def decrypt(
        self,
        ciphertext: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """X25519 does not support direct decryption."""
        raise CryptoEncryptionError(
            algorithm=self.name,
            reason="X25519 is a key exchange-only algorithm",
        )

    async def sign(
        self,
        data: bytes,
        private_key: Any,
        **kwargs: Any,
    ) -> bytes:
        """X25519 does not support signing."""
        raise CryptoSignatureError(
            operation="sign",
            reason="X25519 is a key exchange-only algorithm",
        )

    async def verify(
        self,
        data: bytes,
        signature: bytes,
        public_key: Any,
        **kwargs: Any,
    ) -> bool:
        """X25519 does not support verification."""
        return False

    async def exchange(
        self,
        private_key: bytes,
        peer_public_key: bytes,
    ) -> bytes:
        """
        Perform key exchange.

        Args:
            private_key: Our private key (32 bytes).
            peer_public_key: Peer's public key (32 bytes).

        Returns:
            Shared secret (32 bytes).
        """
        if not _HAS_CRYPTO:
            raise CryptoEncryptionError(
                algorithm=self.name,
                reason="cryptography library not available",
            )

        our_private = X25519PrivateKey.from_private_bytes(private_key)
        their_public = X25519PublicKey.from_public_bytes(peer_public_key)
        shared = our_private.exchange(their_public)
        return shared

    def get_default_params(self) -> Dict[str, Any]:
        return {"key_size": self._key_size}
