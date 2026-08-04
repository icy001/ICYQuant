"""
Crypto platform constants.

Defines algorithm identifiers, key types,
operation types, and default parameters
for the encryption platform.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict


class AlgorithmName(str, Enum):
    """Supported algorithm names."""

    AES_256_GCM = "aes-256-gcm"
    CHACHA20_POLY1305 = "chacha20-poly1305"
    RSA_4096 = "rsa-4096"
    RSA_2048 = "rsa-2048"
    ECDSA_P256 = "ecdsa-p256"
    ECDSA_P384 = "ecdsa-p384"
    ED25519 = "ed25519"
    X25519 = "x25519"
    HMAC_SHA256 = "hmac-sha256"
    HMAC_SHA512 = "hmac-sha512"
    SHA_256 = "sha-256"
    SHA_512 = "sha-512"
    BCRYPT = "bcrypt"


class KeyType(str, Enum):
    """Key classification types."""

    MASTER_KEY = "master_key"
    DATA_ENCRYPTION_KEY = "data_encryption_key"
    SIGNING_KEY = "signing_key"
    VERIFICATION_KEY = "verification_key"
    RSA_PRIVATE_KEY = "rsa_private_key"
    RSA_PUBLIC_KEY = "rsa_public_key"
    AES_KEY = "aes_key"
    CHACHA20_KEY = "chacha20_key"


class OperationType(str, Enum):
    """Cryptographic operation types."""

    ENCRYPT = "encrypt"
    DECRYPT = "decrypt"
    SIGN = "sign"
    VERIFY = "verify"
    HASH = "hash"
    HMAC = "hmac"


class KMSProviderType(str, Enum):
    """KMS provider types."""

    VAULT = "vault"
    AWS_KMS = "aws_kms"
    AZURE_KEY_VAULT = "azure_key_vault"
    GCP_KMS = "gcp_kms"
    LOCAL = "local"


class KeyStatus(str, Enum):
    """Key lifecycle status."""

    ACTIVE = "active"
    ROTATING = "rotating"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"
    ARCHIVED = "archived"
    DELETED = "deleted"


# Algorithm parameter defaults
ALGORITHM_DEFAULTS: Dict[str, Dict[str, Any]] = {
    AlgorithmName.AES_256_GCM.value: {
        "key_size": 32,
        "nonce_size": 12,
        "tag_size": 16,
        "max_data_size": 64 * 1024 * 1024,  # 64MB
    },
    AlgorithmName.CHACHA20_POLY1305.value: {
        "key_size": 32,
        "nonce_size": 12,
        "tag_size": 16,
        "max_data_size": 64 * 1024 * 1024,
    },
    AlgorithmName.RSA_4096.value: {
        "key_size": 4096,
        "padding": "oaep-sha256",
    },
    AlgorithmName.RSA_2048.value: {
        "key_size": 2048,
        "padding": "oaep-sha256",
    },
    AlgorithmName.ED25519.value: {
        "key_size": 32,
    },
    AlgorithmName.X25519.value: {
        "key_size": 32,
    },
    AlgorithmName.HMAC_SHA256.value: {
        "key_size": 32,
        "hash_size": 32,
    },
    AlgorithmName.HMAC_SHA512.value: {
        "key_size": 64,
        "hash_size": 64,
    },
    AlgorithmName.SHA_256.value: {
        "hash_size": 32,
    },
    AlgorithmName.SHA_512.value: {
        "hash_size": 64,
    },
    AlgorithmName.BCRYPT.value: {
        "rounds": 12,
    },
}

# Default algorithm mapping for common use cases
DEFAULT_ENCRYPTION_ALGORITHM = AlgorithmName.AES_256_GCM
DEFAULT_SIGNING_ALGORITHM = AlgorithmName.ED25519
DEFAULT_HASH_ALGORITHM = AlgorithmName.SHA_256
DEFAULT_HMAC_ALGORITHM = AlgorithmName.HMAC_SHA256
DEFAULT_PASSWORD_ALGORITHM = AlgorithmName.BCRYPT

# Envelope encryption parameters
DEFAULT_ENVELOPE_KEY_SIZE = 32  # 256-bit DEK
DEFAULT_ENVELOPE_ALGORITHM = AlgorithmName.AES_256_GCM

# Key rotation defaults
DEFAULT_KEY_ROTATION_DAYS = 365
DEFAULT_MASTER_KEY_ROTATION_DAYS = 365 * 2  # 2 years

# Metrics prefix
METRICS_PREFIX = "icyquant_crypto_"
