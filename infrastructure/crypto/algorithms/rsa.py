"""
RSA asymmetric encryption.

Implements RSA encryption and signing
using the cryptography library, with
support for OAEP padding and
digital signature algorithms.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..constants import AlgorithmName
from ..exceptions import (
    CryptoDecryptionError,
    CryptoEncryptionError,
    CryptoSignatureError,
)
from ..registry import AsymmetricAlgorithm

try:
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import hashes, serialization
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


class RSA2048(AsymmetricAlgorithm):
    """
    RSA-2048 asymmetric encryption and signing.

    Provides 2048-bit RSA with OAEP-SHA256
    encryption and PSS or PKCS1v15 signing.
    """

    name: str = AlgorithmName.RSA_2048.value
    version: str = "1.0.0"

    def __init__(self) -> None:
        self._key_size = 2048
        self._max_plaintext = 190  # OAEP-SHA256 max plaintext for 2048-bit

    async def generate_keypair(self) -> tuple:
        """Generate a new RSA key pair."""
        if not _HAS_CRYPTO:
            raise CryptoEncryptionError(
                algorithm=self.name,
                reason="cryptography library not available",
            )

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self._key_size,
        )
        public_key = private_key.public_key()

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return private_pem, public_pem

    async def encrypt(
        self,
        data: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """
        Encrypt with RSA public key.

        Args:
            data: Plaintext (max 190 bytes for OAEP-SHA256).
            key: PEM-encoded public key.
        """
        if not _HAS_CRYPTO:
            raise CryptoEncryptionError(
                algorithm=self.name,
                reason="cryptography library not available",
            )

        try:
            public_key = serialization.load_pem_public_key(key)
            encrypted = public_key.encrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
            return encrypted
        except Exception as e:
            raise CryptoEncryptionError(
                algorithm=self.name,
                reason=str(e),
            )

    async def decrypt(
        self,
        ciphertext: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """
        Decrypt with RSA private key.

        Args:
            ciphertext: RSA-encrypted ciphertext.
            key: PEM-encoded private key.
        """
        if not _HAS_CRYPTO:
            raise CryptoDecryptionError(
                algorithm=self.name,
                reason="cryptography library not available",
            )

        try:
            private_key = serialization.load_pem_private_key(key, password=None)
            plaintext = private_key.decrypt(
                ciphertext,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
            return plaintext
        except Exception as e:
            raise CryptoDecryptionError(
                algorithm=self.name,
                reason=str(e),
            )

    async def sign(
        self,
        data: bytes,
        private_key: Any,
        **kwargs: Any,
    ) -> bytes:
        """
        Sign data with RSA private key.

        Args:
            data: Data to sign.
            private_key: PEM-encoded private key.
            **kwargs:
                signature_algorithm: 'pss' or 'pkcs1v15' (default: pss).
        """
        if not _HAS_CRYPTO:
            raise CryptoSignatureError(
                operation="sign",
                reason="cryptography library not available",
            )

        try:
            if isinstance(private_key, bytes):
                private_key = serialization.load_pem_private_key(
                    private_key, password=None,
                )

            sig_algo = kwargs.get("signature_algorithm", "pss")

            if sig_algo == "pss":
                signature = private_key.sign(
                    data,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.AUTO,
                    ),
                    hashes.SHA256(),
                )
            else:
                signature = private_key.sign(
                    data,
                    padding.PKCS1v15(),
                    hashes.SHA256(),
                )

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
        Verify RSA signature.

        Args:
            data: Original data.
            signature: Signature bytes.
            public_key: PEM-encoded public key.
            **kwargs:
                signature_algorithm: 'pss' or 'pkcs1v15'.
        """
        if not _HAS_CRYPTO:
            raise CryptoSignatureError(
                operation="verify",
                reason="cryptography library not available",
            )

        try:
            if isinstance(public_key, bytes):
                public_key = serialization.load_pem_public_key(public_key)

            sig_algo = kwargs.get("signature_algorithm", "pss")

            if sig_algo == "pss":
                public_key.verify(
                    signature,
                    data,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.AUTO,
                    ),
                    hashes.SHA256(),
                )
            else:
                public_key.verify(
                    signature,
                    data,
                    padding.PKCS1v15(),
                    hashes.SHA256(),
                )

            return True
        except Exception:
            return False

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "key_size": self._key_size,
            "max_plaintext": self._max_plaintext,
            "padding": "oaep-sha256",
        }


class RSA4096(RSA2048):
    """RSA-4096 variant with larger key size."""

    name: str = AlgorithmName.RSA_4096.value

    def __init__(self) -> None:
        super().__init__()
        self._key_size = 4096
        self._max_plaintext = 624  # OAEP-SHA256 max for 4096-bit
