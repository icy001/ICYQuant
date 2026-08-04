"""
ECDSA signing algorithm.

Implements ECDSA digital signatures
using P-256 and P-384 curves with
the cryptography library.
"""

from __future__ import annotations

from typing import Any, Dict

from ..constants import AlgorithmName
from ..exceptions import CryptoSignatureError
from ..registry import AsymmetricAlgorithm

try:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes, serialization
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


class ECDSAP256(AsymmetricAlgorithm):
    """
    ECDSA with P-256 curve.

    Provides NIST P-256 elliptic curve
    digital signatures with SHA-256
    hash, offering 128-bit security
    level with compact key sizes.
    """

    name: str = AlgorithmName.ECDSA_P256.value
    version: str = "1.0.0"

    def __init__(self) -> None:
        self._curve = ec.SECP256R1()
        self._hash = hashes.SHA256()

    async def generate_keypair(self) -> tuple:
        """Generate a new ECDSA P-256 key pair."""
        if not _HAS_CRYPTO:
            raise CryptoSignatureError(
                operation="generate",
                reason="cryptography library not available",
            )

        private_key = ec.generate_private_key(self._curve)
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
        """ECDSA does not support encryption."""
        raise CryptoSignatureError(
            operation="encrypt",
            reason="ECDSA is a signing-only algorithm",
        )

    async def decrypt(
        self,
        ciphertext: bytes,
        key: bytes,
        **kwargs: Any,
    ) -> bytes:
        """ECDSA does not support decryption."""
        raise CryptoSignatureError(
            operation="decrypt",
            reason="ECDSA is a signing-only algorithm",
        )

    async def sign(
        self,
        data: bytes,
        private_key: Any,
        **kwargs: Any,
    ) -> bytes:
        """
        Sign data with ECDSA P-256.

        Args:
            data: Data to sign.
            private_key: PEM-encoded private key.
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

            signature = private_key.sign(
                data,
                ec.ECDSA(self._hash),
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
        Verify ECDSA P-256 signature.

        Args:
            data: Original data.
            signature: Signature to verify.
            public_key: PEM-encoded public key.
        """
        if not _HAS_CRYPTO:
            return False

        try:
            if isinstance(public_key, bytes):
                public_key = serialization.load_pem_public_key(public_key)

            public_key.verify(
                signature,
                data,
                ec.ECDSA(self._hash),
            )
            return True
        except Exception:
            return False

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "curve": "secp256r1",
            "hash": "sha-256",
            "key_size": 32,
        }


class ECDSAP384(ECDSAP256):
    """ECDSA with P-384 curve."""

    name: str = AlgorithmName.ECDSA_P384.value

    def __init__(self) -> None:
        self._curve = ec.SECP384R1()
        self._hash = hashes.SHA384()
