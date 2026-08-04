"""
Crypto platform exceptions.

Defines the exception hierarchy for
the encryption platform, enabling precise
error handling for cryptographic operations.
"""

from __future__ import annotations

from typing import List, Optional


class CryptoError(Exception):
    """Base exception for all crypto platform errors."""

    def __init__(self, message: str = "", **kwargs: object) -> None:
        self._details = kwargs
        msg = message or self._build_message(**kwargs)
        super().__init__(msg)

    @staticmethod
    def _build_message(**kwargs: object) -> str:
        parts: list[str] = ["Crypto error"]
        for key, value in kwargs.items():
            if value:
                parts.append(f"{key}={value}")
        return ", ".join(parts)

    @property
    def algorithm(self) -> str:
        return str(self._details.get("algorithm", ""))

    @property
    def reason(self) -> str:
        return str(self._details.get("reason", ""))

    @property
    def key_id(self) -> str:
        return str(self._details.get("key_id", ""))

    @property
    def operation(self) -> str:
        return str(self._details.get("operation", ""))

    @property
    def provider(self) -> str:
        return str(self._details.get("provider", ""))


class CryptoEncryptionError(CryptoError):
    """Raised when encryption fails."""

    def __init__(
        self,
        algorithm: str = "",
        reason: str = "",
    ) -> None:
        msg = "Encryption failed"
        if algorithm:
            msg += f" [{algorithm}]"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, algorithm=algorithm, reason=reason)


class CryptoDecryptionError(CryptoError):
    """Raised when decryption fails."""

    def __init__(
        self,
        algorithm: str = "",
        reason: str = "",
    ) -> None:
        msg = "Decryption failed"
        if algorithm:
            msg += f" [{algorithm}]"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, algorithm=algorithm, reason=reason)


class CryptoSignatureError(CryptoError):
    """Raised when signing or verification fails."""

    def __init__(
        self,
        operation: str = "",
        reason: str = "",
    ) -> None:
        msg = f"Signature operation failed: {operation}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, operation=operation, reason=reason)


class CryptoHashError(CryptoError):
    """Raised when hashing fails."""


class CryptoKeyError(CryptoError):
    """Raised when key operations fail."""

    def __init__(
        self,
        key_id: str = "",
        operation: str = "",
        reason: str = "",
    ) -> None:
        msg = f"Key operation failed: {operation}"
        if key_id:
            msg += f" (key: {key_id})"
        if reason:
            msg += f": {reason}"
        super().__init__(
            msg, key_id=key_id, operation=operation, reason=reason
        )


class CryptoKeyNotFoundError(CryptoKeyError):
    """Raised when a key is not found."""

    def __init__(
        self,
        key_id: str,
        version: Optional[int] = None,
    ) -> None:
        msg = f"Key not found: {key_id}"
        if version is not None:
            msg += f" v{version}"
        super().__init__(
            key_id=key_id,
            operation="lookup",
            reason=msg,
        )
        self.version = version


class CryptoKeyRotationError(CryptoKeyError):
    """Raised when key rotation fails."""


class CryptoKMSError(CryptoError):
    """Raised when KMS provider operations fail."""

    def __init__(
        self,
        provider: str = "",
        operation: str = "",
        reason: str = "",
    ) -> None:
        msg = f"KMS '{provider}' operation '{operation}' failed"
        if reason:
            msg += f": {reason}"
        super().__init__(
            msg,
            provider=provider,
            operation=operation,
            reason=reason,
        )


class CryptoEnvelopeError(CryptoError):
    """Raised when envelope encryption fails."""

    def __init__(
        self,
        stage: str = "",
        reason: str = "",
    ) -> None:
        msg = f"Envelope encryption failed at '{stage}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, stage=stage, reason=reason)

    @property
    def stage(self) -> str:
        return str(self._details.get("stage", ""))


class CryptoAlgorithmNotSupportedError(CryptoError):
    """Raised when an algorithm is not supported."""

    def __init__(self, algorithm: str) -> None:
        super().__init__(
            f"Algorithm not supported: {algorithm}",
            algorithm=algorithm,
        )


class CryptoConfigurationError(CryptoError):
    """Raised when crypto configuration is invalid."""


class CryptoValidationError(CryptoError):
    """Raised when crypto validation fails."""

    def __init__(
        self,
        errors: Optional[List[str]] = None,
    ) -> None:
        self.errors = errors or []
        super().__init__(
            f"Validation failed: {', '.join(self.errors)}"
        )
