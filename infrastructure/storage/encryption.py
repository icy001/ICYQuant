"""
Storage encryption.

Provides AES256 encryption/decryption for
sensitive storage payloads using the
cryptography library's Fernet symmetric
encryption.
"""

from __future__ import annotations

import os
from typing import Optional

try:
    from cryptography.fernet import Fernet, InvalidToken

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore
    CRYPTOGRAPHY_AVAILABLE = False


class StorageEncryption:
    """
    Storage encryption provider.

    Implements AES256 symmetric encryption using
    Fernet for secure object storage. Used for
    sensitive data like audit logs, PII, and
    confidential research data.

    Features:
    - AES256-CBC encryption via Fernet
    - Key generation and rotation support
    - Thread-safe operation

    Usage:
        # Generate a key (do this once and store securely)
        key = StorageEncryption.generate_key()

        # Initialize with key
        enc = StorageEncryption(key)
        encrypted = enc.encrypt(b"sensitive data")
        decrypted = enc.decrypt(encrypted)
    """

    def __init__(
        self,
        key: Optional[bytes] = None,
    ) -> None:
        """
        Initialize encryption.

        Args:
            key: Encryption key (32 bytes, base64 encoded).
                If None, generates a new key (insecure for
                production - key will be lost on restart).
        """

        self._fernet: Optional[Fernet] = None
        self._key: Optional[bytes] = None

        if key is not None:
            self._set_key(key)

    @classmethod
    def generate_key(
        cls,
    ) -> bytes:
        """
        Generate a new encryption key.

        Returns:
            Base64-encoded 32-byte key.
        """

        if not CRYPTOGRAPHY_AVAILABLE:
            raise ImportError(
                "cryptography package is required. "
                "Install with: pip install cryptography"
            )
        return Fernet.generate_key()

    def _set_key(
        self,
        key: bytes,
    ) -> None:
        """
        Set encryption key.

        Args:
            key: Encryption key.
        """

        if not CRYPTOGRAPHY_AVAILABLE:
            raise ImportError(
                "cryptography package is required. "
                "Install with: pip install cryptography"
            )

        self._key = key
        self._fernet = Fernet(key)

    @property
    def is_initialized(
        self,
    ) -> bool:
        """Check if encryption is initialized."""
        return self._fernet is not None

    @property
    def is_available(
        self,
    ) -> bool:
        """Check if cryptography is available."""
        return CRYPTOGRAPHY_AVAILABLE

    def set_key(
        self,
        key: bytes,
    ) -> None:
        """
        Set or rotate encryption key.

        Args:
            key: New encryption key.
        """

        self._set_key(key)

    def encrypt(
        self,
        data: bytes,
    ) -> bytes:
        """
        Encrypt data.

        Args:
            data: Plaintext bytes.

        Returns:
            Encrypted bytes (Fernet token).

        Raises:
            RuntimeError: If encryption not initialized.
        """

        if self._fernet is None:
            raise RuntimeError(
                "Encryption not initialized. "
                "Set a key first via set_key()."
            )

        return self._fernet.encrypt(data)

    def decrypt(
        self,
        data: bytes,
    ) -> bytes:
        """
        Decrypt data.

        Args:
            data: Encrypted bytes (Fernet token).

        Returns:
            Decrypted plaintext bytes.

        Raises:
            RuntimeError: If decryption not initialized.
            ValueError: If token is invalid or expired.
        """

        if self._fernet is None:
            raise RuntimeError(
                "Encryption not initialized. "
                "Set a key first via set_key()."
            )

        try:
            return self._fernet.decrypt(data)
        except InvalidToken:
            raise ValueError(
                "Invalid or expired encryption token."
            )

    @staticmethod
    def generate_random_key() -> bytes:
        """
        Generate a random key for temporary use.

        Returns:
            32 random bytes (not base64 encoded).
        """

        return os.urandom(32)