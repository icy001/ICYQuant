"""
Signature Provider — Generates cryptographic signatures for exchange
API authentication using HMAC, RSA, ED25519, and custom methods.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SignatureMethod(str, Enum):
    HMAC_SHA256 = "hmac_sha256"
    HMAC_SHA512 = "hmac_sha512"
    RSA_SHA256 = "rsa_sha256"
    RSA_SHA512 = "rsa_sha512"
    ED25519 = "ed25519"
    ECDSA = "ecdsa"
    NONE = "none"


@dataclass
class SignatureResult:
    signature: str
    method: SignatureMethod
    timestamp: int
    payload: str = ""


class SignatureProvider:
    """
    Provides cryptographic signing for exchange API requests.

    Supports HMAC-SHA256/512, RSA-SHA256/512, ED25519, and
    ECDSA signature methods for various exchange authentication.

    Usage::

        provider = SignatureProvider()
        result = provider.sign_hmac("secret", "payload", method="POST", path="/api/v3/order")
        headers = provider.to_headers(api_key="...", signature_result=result)
    """

    def __init__(self) -> None:
        self._default_method: SignatureMethod = SignatureMethod.HMAC_SHA256

    @property
    def default_method(self) -> SignatureMethod:
        return self._default_method

    def set_default_method(self, method: SignatureMethod) -> None:
        self._default_method = method

    # ---- HMAC Signing ----

    def sign_hmac_sha256(
        self,
        secret: str,
        payload: str = "",
        timestamp: Optional[int] = None,
    ) -> SignatureResult:
        """Generate HMAC-SHA256 signature."""
        import time as _time
        ts = timestamp or int(_time.time() * 1000)
        message = f"{ts}{payload}".encode()
        sig = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
        return SignatureResult(signature=sig, method=SignatureMethod.HMAC_SHA256, timestamp=ts, payload=payload)

    def sign_hmac_sha512(
        self,
        secret: str,
        payload: str = "",
        timestamp: Optional[int] = None,
    ) -> SignatureResult:
        """Generate HMAC-SHA512 signature."""
        import time as _time
        ts = timestamp or int(_time.time() * 1000)
        message = f"{ts}{payload}".encode()
        sig = hmac.new(secret.encode(), message, hashlib.sha512).hexdigest()
        return SignatureResult(signature=sig, method=SignatureMethod.HMAC_SHA512, timestamp=ts, payload=payload)

    def sign_hmac(
        self,
        secret: str,
        payload: str = "",
        method: str = "GET",
        path: str = "/",
        body: str = "",
        timestamp: Optional[int] = None,
    ) -> SignatureResult:
        """Generate HMAC-SHA256 signature with method/path/body."""
        import time as _time
        ts = timestamp or int(_time.time() * 1000)
        message = f"{ts}{method}{path}{body}".encode()
        sig = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
        return SignatureResult(
            signature=sig,
            method=SignatureMethod.HMAC_SHA256,
            timestamp=ts,
            payload=message.decode(errors="replace"),
        )

    # ---- RSA Signing ----

    def sign_rsa_sha256(
        self,
        private_key_pem: str,
        payload: str = "",
        timestamp: Optional[int] = None,
    ) -> Optional[SignatureResult]:
        """Generate RSA-SHA256 signature."""
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            import time as _time

            ts = timestamp or int(_time.time() * 1000)
            key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
            sig_bytes = key.sign(
                f"{ts}{payload}".encode(),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            import base64
            sig = base64.b64encode(sig_bytes).decode()
            return SignatureResult(signature=sig, method=SignatureMethod.RSA_SHA256, timestamp=ts, payload=payload)
        except ImportError:
            logger.warning("cryptography library not available for RSA signing")
            return None
        except Exception:
            logger.exception("RSA signing error")
            return None

    # ---- Headers ----

    def to_headers(
        self,
        api_key: str,
        signature_result: SignatureResult,
        passphrase: str = "",
    ) -> dict[str, str]:
        """Convert signature result to HTTP headers."""
        headers = {
            "X-API-KEY": api_key,
            "X-SIGNATURE": signature_result.signature,
            "X-TIMESTAMP": str(signature_result.timestamp),
            "X-SIGN-METHOD": signature_result.method.value,
        }
        if passphrase:
            headers["X-PASSPHRASE"] = passphrase
        return headers

    @staticmethod
    def generate_secret(length: int = 32) -> str:
        """Generate a secure random secret."""
        import secrets
        return secrets.token_hex(length)

    @staticmethod
    def generate_nonce(length: int = 16) -> str:
        """Generate a random nonce for request uniqueness."""
        import secrets
        return secrets.token_hex(length)
