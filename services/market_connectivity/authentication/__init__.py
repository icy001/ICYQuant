"""
Authentication Framework — Unified authentication layer for exchange
connectivity supporting API Key, HMAC, RSA, JWT, and certificate-based auth.
"""

from .credential_manager import CredentialManager, Credential, CredentialType
from .api_key_provider import APIKeyProvider, APIKey
from .token_manager import TokenManager, Token, TokenType
from .signature_provider import SignatureProvider, SignatureMethod
from .certificate_manager import CertificateManager, Certificate, CertificateType

__all__ = [
    "CredentialManager",
    "Credential",
    "CredentialType",
    "APIKeyProvider",
    "APIKey",
    "TokenManager",
    "Token",
    "TokenType",
    "SignatureProvider",
    "SignatureMethod",
    "CertificateManager",
    "Certificate",
    "CertificateType",
]
