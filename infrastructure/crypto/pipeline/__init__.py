"""
Cryptographic operation pipelines.

Provides pipeline orchestration for
encrypt, decrypt, sign, verify, hash,
and key rotation operations, integrating
algorithm selection with KMS providers
and envelope encryption.
"""

from __future__ import annotations

from .encrypt import EncryptionPipeline, EncryptionResult
from .decrypt import DecryptionPipeline, DecryptionResult
from .sign import SigningPipeline, SigningResult
from .verify import VerificationPipeline, VerificationResult
from .hash import HashPipeline, HashResult, HMACResult
from .rotate import KeyRotationPipeline, KeyRotationResult


__all__ = [
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
]
