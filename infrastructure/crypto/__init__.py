"""
Crypto platform.

Provides production-grade cryptographic
services including unified encryption,
decryption, signing, verification,
hashing, and key management with
envelope encryption and KMS integration.

Architecture:
    CryptoManager (high-level API)
          |
    +---> CryptoService (unified crypto)
    |       +---> AlgorithmRegistry
    |       +---> EncryptionPipeline
    |       +---> DecryptionPipeline
    |       +---> SigningPipeline
    |       +---> VerificationPipeline
    |       +---> HashPipeline
    |       +---> KeyRotationPipeline
    +---> EnvelopeEncryption
    +---> KeyStore (metadata)
    +---> Keyring (material)
    +---> KMS Provider
    +---> CryptoMetrics
    +---> CryptoDiagnostics

Usage:
    from infrastructure.crypto import CryptoManager

    manager = CryptoManager()
    await manager.initialize()
    encrypted = await manager.encrypt(b"data", "key-id")
"""

from __future__ import annotations

# Constants
from .constants import (
    AlgorithmName,
    KeyType,
    OperationType,
    KMSProviderType,
    KeyStatus,
)

# Config
from .config import CryptoConfig, AlgorithmConfig, KMSConfig

# Exceptions
from .exceptions import (
    CryptoError,
    CryptoEncryptionError,
    CryptoDecryptionError,
    CryptoSignatureError,
    CryptoHashError,
    CryptoKeyError,
    CryptoKeyNotFoundError,
    CryptoKeyRotationError,
    CryptoKMSError,
    CryptoEnvelopeError,
    CryptoAlgorithmNotSupportedError,
    CryptoConfigurationError,
    CryptoValidationError,
)

# Registry
from .registry import (
    CryptoAlgorithm,
    AsymmetricAlgorithm,
    HashAlgorithm,
    HMACAlgorithm,
    PasswordHashAlgorithm,
    AlgorithmRegistry,
)

# Factory
from .factory import CryptoFactory

# Algorithms
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

# KMS
from .kms import (
    KMSProvider,
    KMSKeyInfo,
    KMSProviderHealth,
    LocalKMSProvider,
    VaultKMSProvider,
    AWSKMSProvider,
    AzureKeyVaultProvider,
    GCPKMSProvider,
)

# Envelope
from .envelope import EnvelopeEncryption, EnvelopeEncryptedData

# Key management
from .keystore import KeyStore, KeyMetadata, KeyVersion
from .keyring import Keyring, StoredKey

# Pipelines
from .pipeline import (
    EncryptionPipeline,
    EncryptionResult,
    DecryptionPipeline,
    DecryptionResult,
    SigningPipeline,
    SigningResult,
    VerificationPipeline,
    VerificationResult,
    HashPipeline,
    HashResult,
    HMACResult,
    KeyRotationPipeline,
    KeyRotationResult,
)

# Service and Manager
from .service import CryptoService
from .manager import CryptoManager

# Support
from .metrics import CryptoMetrics
from .health import CryptoHealthCheck
from .diagnostics import CryptoDiagnostics

# Bootstrap and Infrastructure
from .bootstrap import CryptoBootstrap
from .container import CryptoContainer, create_default_container
from .lifecycle import CryptoLifecycleState, CryptoLifecycle
from .scheduler import CryptoScheduler
from .telemetry import CryptoTelemetry, CryptoTraceSpan
from .monitoring import CryptoMonitoring
from .integrity import CryptoIntegrity, CryptoIntegrityResult
from .protection import CryptoProtection, ProtectionCircuitState
from .recovery import CryptoRecovery, RecoveryState


__all__ = [
    # Constants
    "AlgorithmName",
    "KeyType",
    "OperationType",
    "KMSProviderType",
    "KeyStatus",
    # Config
    "CryptoConfig",
    "AlgorithmConfig",
    "KMSConfig",
    # Exceptions
    "CryptoError",
    "CryptoEncryptionError",
    "CryptoDecryptionError",
    "CryptoSignatureError",
    "CryptoHashError",
    "CryptoKeyError",
    "CryptoKeyNotFoundError",
    "CryptoKeyRotationError",
    "CryptoKMSError",
    "CryptoEnvelopeError",
    "CryptoAlgorithmNotSupportedError",
    "CryptoConfigurationError",
    "CryptoValidationError",
    # Registry
    "CryptoAlgorithm",
    "AsymmetricAlgorithm",
    "HashAlgorithm",
    "HMACAlgorithm",
    "PasswordHashAlgorithm",
    "AlgorithmRegistry",
    # Factory
    "CryptoFactory",
    # Algorithms
    "AES256GCM",
    "ChaCha20Poly1305",
    "RSA2048",
    "RSA4096",
    "ECDSAP256",
    "ECDSAP384",
    "Ed25519",
    "X25519",
    "HMACSHA256",
    "HMACSHA512",
    "SHA256",
    "SHA512",
    "BcryptPassword",
    # KMS
    "KMSProvider",
    "KMSKeyInfo",
    "KMSProviderHealth",
    "LocalKMSProvider",
    "VaultKMSProvider",
    "AWSKMSProvider",
    "AzureKeyVaultProvider",
    "GCPKMSProvider",
    # Envelope
    "EnvelopeEncryption",
    "EnvelopeEncryptedData",
    # Key management
    "KeyStore",
    "KeyMetadata",
    "KeyVersion",
    "Keyring",
    "StoredKey",
    # Pipelines
    "EncryptionPipeline",
    "EncryptionResult",
    "DecryptionPipeline",
    "DecryptionResult",
    "SigningPipeline",
    "SigningResult",
    "VerificationPipeline",
    "VerificationResult",
    "HashPipeline",
    "HashResult",
    "HMACResult",
    "KeyRotationPipeline",
    "KeyRotationResult",
    # Service and Manager
    "CryptoService",
    "CryptoManager",
    # Support
    "CryptoMetrics",
    "CryptoHealthCheck",
    "CryptoDiagnostics",
    # Bootstrap and Infrastructure
    "CryptoBootstrap",
    "CryptoContainer",
    "create_default_container",
    "CryptoLifecycleState",
    "CryptoLifecycle",
    "CryptoScheduler",
    "CryptoTelemetry",
    "CryptoTraceSpan",
    "CryptoMonitoring",
    "CryptoIntegrity",
    "CryptoIntegrityResult",
    "CryptoProtection",
    "ProtectionCircuitState",
    "CryptoRecovery",
    "RecoveryState",
]
