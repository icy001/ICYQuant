"""Marketplace signature verification.

Provides :class:`MarketplaceSignature` for creating and verifying
package and repository signatures using SHA256 hashing with RSA
support via the ``cryptography`` library (HMAC-SHA256 fallback
for environments where ``cryptography`` is not installed).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SUPPORTED_ALGORITHMS = ["SHA256", "RSA", "ECDSA"]


class MarketplaceSignature:
    """Creates and verifies marketplace package and repository signatures.

    Supports RSA-based signatures via the ``cryptography`` library
    with an automatic fallback to HMAC-SHA256 when the ``cryptography``
    package is not installed.  All verification results are recorded
    for audit purposes.

    Attributes:
        _failures: Accumulates verification failure records.
        _lock: Thread-safe reentrant lock.
        _use_rsa: Whether the ``cryptography`` package is available.
    """

    def __init__(self) -> None:
        self._failures: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        self._max_failures = 1000
        self._use_rsa = False

        try:
            from cryptography.hazmat.primitives.asymmetric import rsa, padding
            from cryptography.hazmat.primitives import hashes, serialization

            self._use_rsa = True
            self._rsa_mod = rsa
            self._rsa_padding = padding
            self._rsa_hashes = hashes
            self._rsa_serialization = serialization
            logger.info(
                "MarketplaceSignature initialized with RSA support"
            )
        except ImportError:
            logger.warning(
                "cryptography package not available; using HMAC-SHA256 "
                "fallback for signature verification"
            )

    def sign_package(self, package_path: str, private_key: str) -> str:
        """Create a signature for a package file.

        Args:
            package_path: Filesystem path to the package to sign.
            private_key: The PEM-encoded private key string.

        Returns:
            A base64-encoded signature string.

        Raises:
            FileNotFoundError: If the package path does not exist.
            ValueError: If signing fails.
        """
        if not os.path.exists(package_path):
            raise FileNotFoundError(
                f"Package not found: {package_path}"
            )
        data = self._read_file(package_path)
        try:
            if self._use_rsa:
                signature = self._rsa_sign(data, private_key)
            else:
                signature = self._hmac_sign(data, private_key)
            return base64.b64encode(signature).decode("utf-8")
        except Exception as exc:
            raise ValueError(
                f"Failed to sign package '{package_path}': {exc}"
            ) from exc

    def verify_package(
        self,
        package_path: str,
        signature: str,
        public_key: str,
    ) -> bool:
        """Verify a package's signature.

        Args:
            package_path: Filesystem path to the signed package.
            signature: The base64-encoded signature string.
            public_key: The PEM-encoded public key string.

        Returns:
            True if the signature is valid, False otherwise.
        """
        try:
            if not os.path.exists(package_path):
                self._record_failure(
                    package_path, "file_not_found", {}
                )
                return False
            data = self._read_file(package_path)
            signature_bytes = base64.b64decode(signature)

            if self._use_rsa:
                valid = self._rsa_verify(
                    data, signature_bytes, public_key
                )
            else:
                valid = self._hmac_verify(
                    data, signature_bytes, public_key
                )

            if not valid:
                self._record_failure(
                    package_path, "signature_mismatch", {}
                )
            return valid
        except Exception as exc:
            self._record_failure(
                package_path, "verify_error", {"error": str(exc)}
            )
            logger.warning(
                "Package verification error for '%s': %s",
                package_path,
                exc,
            )
            return False

    def verify_repository(
        self,
        repo_url: str,
        signature: str,
        public_key: str,
    ) -> bool:
        """Verify a repository's signature.

        Args:
            repo_url: The repository URL (used as the data to verify).
            signature: The base64-encoded signature string.
            public_key: The PEM-encoded public key string.

        Returns:
            True if the signature is valid, False otherwise.
        """
        try:
            data = repo_url.encode("utf-8")
            signature_bytes = base64.b64decode(signature)

            if self._use_rsa:
                valid = self._rsa_verify(
                    data, signature_bytes, public_key
                )
            else:
                valid = self._hmac_verify(
                    data, signature_bytes, public_key
                )

            if not valid:
                self._record_failure(
                    repo_url, "repository_signature_mismatch", {}
                )
            return valid
        except Exception as exc:
            self._record_failure(
                repo_url, "repository_verify_error", {"error": str(exc)}
            )
            logger.warning(
                "Repository verification error for '%s': %s",
                repo_url,
                exc,
            )
            return False

    def compute_hash(self, data: bytes) -> str:
        """Compute a SHA256 hash of the given data.

        Args:
            data: The bytes to hash.

        Returns:
            A hex-encoded SHA256 hash string.
        """
        return hashlib.sha256(data).hexdigest()

    def compute_package_hash(self, package_path: str) -> str:
        """Compute a SHA256 hash of a package file.

        Args:
            package_path: Filesystem path to the package.

        Returns:
            A hex-encoded SHA256 hash string.

        Raises:
            FileNotFoundError: If the package path does not exist.
        """
        if not os.path.exists(package_path):
            raise FileNotFoundError(
                f"Package not found: {package_path}"
            )
        data = self._read_file(package_path)
        return self.compute_hash(data)

    def get_supported_algorithms(self) -> List[str]:
        """Return the list of supported signature algorithms.

        Returns:
            A list of algorithm name strings.
        """
        return list(SUPPORTED_ALGORITHMS)

    def get_stats(self) -> Dict[str, Any]:
        """Return signature verifier statistics.

        Returns:
            A dictionary with RSA availability and failure counts.
        """
        with self._lock:
            return {
                "use_rsa": self._use_rsa,
                "supported_algorithms": self.get_supported_algorithms(),
                "total_failures": len(self._failures),
                "recent_failures": self._failures[-10:],
            }

    def _read_file(self, path: str) -> bytes:
        """Read a file and return its bytes content.

        Args:
            path: Filesystem path to read.

        Returns:
            The file contents as bytes.
        """
        with open(path, "rb") as fh:
            return fh.read()

    def _rsa_sign(
        self, data: bytes, private_key_pem: str
    ) -> bytes:
        """Sign data using RSA.

        Args:
            data: The bytes to sign.
            private_key_pem: PEM-encoded private key.

        Returns:
            The signature bytes.
        """
        pk = self._rsa_serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"), password=None
        )
        signature = pk.sign(
            data,
            self._rsa_padding.PKCS1v15(),
            self._rsa_hashes.SHA256(),
        )
        return signature

    def _rsa_verify(
        self,
        data: bytes,
        signature: bytes,
        public_key_pem: str,
    ) -> bool:
        """Verify an RSA signature.

        Args:
            data: The original signed bytes.
            signature: The signature bytes.
            public_key_pem: PEM-encoded public key.

        Returns:
            True if the signature is valid.
        """
        try:
            pk = self._rsa_serialization.load_pem_public_key(
                public_key_pem.encode("utf-8")
            )
            pk.verify(
                signature,
                data,
                self._rsa_padding.PKCS1v15(),
                self._rsa_hashes.SHA256(),
            )
            return True
        except Exception:
            return False

    def _hmac_sign(self, data: bytes, key: str) -> bytes:
        """Sign data using HMAC-SHA256.

        Args:
            data: The bytes to sign.
            key: The HMAC key string.

        Returns:
            The HMAC signature bytes.
        """
        return hmac.new(
            key.encode("utf-8"), data, hashlib.sha256
        ).digest()

    def _hmac_verify(
        self, data: bytes, signature: bytes, key: str
    ) -> bool:
        """Verify an HMAC-SHA256 signature.

        Args:
            data: The original signed bytes.
            signature: The signature bytes.
            key: The HMAC key string.

        Returns:
            True if the signature is valid.
        """
        expected = hmac.new(
            key.encode("utf-8"), data, hashlib.sha256
        ).digest()
        return hmac.compare_digest(expected, signature)

    def _record_failure(
        self,
        target: str,
        failure_type: str,
        details: Dict[str, Any],
    ) -> None:
        """Record a verification failure for audit.

        Args:
            target: The package path or repo URL.
            failure_type: The type of failure.
            details: Additional failure details.
        """
        entry: Dict[str, Any] = {
            "target": target,
            "failure_type": failure_type,
            "details": details,
            "timestamp": time.time(),
        }
        with self._lock:
            self._failures.append(entry)
            if len(self._failures) > self._max_failures:
                self._failures = self._failures[-self._max_failures:]