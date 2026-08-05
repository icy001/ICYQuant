"""Plugin signature verification.

Provides :class:`SignatureVerifier` for creating and verifying
plugin signatures using RSA (via the ``cryptography`` library)
with an HMAC-SHA256 fallback for environments where
``cryptography`` is not installed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from ..exceptions import PluginSecurityError, PluginSignatureError

logger = logging.getLogger(__name__)


class SignatureVerifier:
    """Creates and verifies plugin signatures.

    Supports RSA-based signatures via the ``cryptography``
    library (preferred) with an automatic fallback to
    HMAC-SHA256 when the ``cryptography`` package is not
    installed.  All verification failures are recorded for
    audit purposes.

    Attributes:
        _key_cache: Maps plugin_id to (public_key, private_key) tuple.
        _failures: Accumulates verification failure records.
        _lock: Thread-safe reentrant lock.
        _use_rsa: Whether the ``cryptography`` package is available.
    """

    def __init__(self) -> None:
        self._key_cache: Dict[str, Tuple[str, Optional[str]]] = {}
        self._failures: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        self._max_failures = 1000
        self._use_rsa = False
        self._public_key: Any = None
        self._private_key: Any = None

        try:
            from cryptography.hazmat.primitives.asymmetric import rsa, padding
            from cryptography.hazmat.primitives import hashes, serialization

            self._use_rsa = True
            self._rsa_mod = rsa
            self._rsa_padding = padding
            self._rsa_hashes = hashes
            self._rsa_serialization = serialization
            logger.info(
                "SignatureVerifier initialized with RSA support"
            )
        except ImportError:
            logger.warning(
                "cryptography package not available; using HMAC-SHA256 "
                "fallback for signature verification"
            )

    def sign(self, plugin_id: str, private_key: str) -> str:
        """Create a signature for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            private_key: The PEM-encoded private key string.

        Returns:
            A base64-encoded signature string.

        Raises:
            PluginSignatureError: If signing fails.
        """
        try:
            data = plugin_id.encode("utf-8")
            if self._use_rsa:
                signature = self._rsa_sign(data, private_key)
            else:
                signature = self._hmac_sign(data, private_key)
            return base64.b64encode(signature).decode("utf-8")
        except Exception as exc:
            raise PluginSignatureError(
                f"Failed to sign plugin '{plugin_id}': {exc}"
            ) from exc

    def verify(
        self,
        plugin_id: str,
        signature: str,
        public_key: Optional[str] = None,
    ) -> bool:
        """Verify a plugin's signature.

        Args:
            plugin_id: Unique identifier for the plugin.
            signature: The base64-encoded signature string.
            public_key: Optional PEM-encoded public key.  If not
                provided, the key is looked up from the internal
                cache.

        Returns:
            True if the signature is valid, False otherwise.
        """
        try:
            data = plugin_id.encode("utf-8")
            signature_bytes = base64.b64decode(signature)

            if public_key is None:
                cached = self._key_cache.get(plugin_id)
                if cached:
                    public_key = cached[0]

            if public_key is None:
                self._record_failure(
                    plugin_id, "no_public_key", {}
                )
                logger.warning(
                    "No public key available for plugin %s", plugin_id
                )
                return False

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
                    plugin_id, "signature_mismatch", {}
                )

            return valid
        except Exception as exc:
            self._record_failure(
                plugin_id, "verify_error", {"error": str(exc)}
            )
            logger.warning(
                "Signature verification error for plugin %s: %s",
                plugin_id, exc,
            )
            return False

    def verify_manifest(
        self,
        manifest_data: Dict[str, Any],
        signature: str,
    ) -> bool:
        """Verify a plugin manifest against its signature.

        The manifest is serialized to a deterministic JSON string
        before verification.

        Args:
            manifest_data: The manifest dictionary to verify.
            signature: The base64-encoded signature string.

        Returns:
            True if the manifest signature is valid, False otherwise.
        """
        try:
            canonical = json.dumps(
                manifest_data,
                sort_keys=True,
                separators=(",", ":"),
            )
            plugin_id = manifest_data.get("id", "unknown")
            data = canonical.encode("utf-8")
            signature_bytes = base64.b64decode(signature)

            cached = self._key_cache.get(plugin_id)
            public_key = cached[0] if cached else None

            if public_key is None:
                self._record_failure(
                    plugin_id, "manifest_no_public_key", {}
                )
                return False

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
                    plugin_id, "manifest_signature_mismatch", {}
                )

            return valid
        except Exception as exc:
            logger.warning(
                "Manifest verification error: %s", exc
            )
            return False

    def generate_keypair(self) -> Tuple[str, str]:
        """Generate an RSA keypair for plugin signing.

        Returns:
            A tuple of (public_key_pem, private_key_pem) strings.

        Raises:
            PluginSecurityError: If keypair generation fails.
        """
        try:
            if self._use_rsa:
                return self._generate_rsa_keypair()
            return self._generate_hmac_keypair()
        except Exception as exc:
            raise PluginSecurityError(
                f"Failed to generate keypair: {exc}"
            ) from exc

    def load_key(self, path: str) -> str:
        """Load a PEM-encoded key from a file.

        Args:
            path: Filesystem path to the key file.

        Returns:
            The key content as a string.

        Raises:
            PluginSecurityError: If the file cannot be read.
        """
        try:
            with open(path, "r", encoding="utf-8") as fh:
                key = fh.read().strip()
            logger.debug("Loaded key from %s", path)
            return key
        except (IOError, OSError) as exc:
            raise PluginSecurityError(
                f"Failed to load key from '{path}': {exc}"
            ) from exc

    def save_key(self, key: str, path: str) -> None:
        """Save a PEM-encoded key to a file.

        Args:
            key: The PEM-encoded key string to save.
            path: Filesystem path to write the key file.

        Raises:
            PluginSecurityError: If the file cannot be written.
        """
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(key)
            logger.info("Saved key to %s", path)
        except (IOError, OSError) as exc:
            raise PluginSecurityError(
                f"Failed to save key to '{path}': {exc}"
            ) from exc

    def register_key(
        self,
        plugin_id: str,
        public_key: str,
        private_key: Optional[str] = None,
    ) -> None:
        """Register a key pair for a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            public_key: The PEM-encoded public key.
            private_key: Optional PEM-encoded private key.
        """
        with self._lock:
            self._key_cache[plugin_id] = (public_key, private_key)
            logger.debug(
                "Registered key pair for plugin %s", plugin_id
            )

    def get_registered_plugins(self) -> List[str]:
        """Get the list of plugin IDs with registered keys.

        Returns:
            A sorted list of plugin IDs.
        """
        with self._lock:
            return sorted(self._key_cache.keys())

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

    def _generate_rsa_keypair(self) -> Tuple[str, str]:
        """Generate an RSA keypair.

        Returns:
            A tuple of (public_key_pem, private_key_pem).
        """
        private_key = self._rsa_mod.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        private_pem = private_key.private_bytes(
            encoding=self._rsa_serialization.Encoding.PEM,
            format=self._rsa_serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=self._rsa_serialization.NoEncryption(),
        ).decode("utf-8")
        public_pem = private_key.public_key().public_bytes(
            encoding=self._rsa_serialization.Encoding.PEM,
            format=self._rsa_serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        return (public_pem, private_pem)

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

    def _generate_hmac_keypair(self) -> Tuple[str, str]:
        """Generate an HMAC key pair (two random keys).

        Returns:
            A tuple of (public_key, private_key) strings.
        """
        private_key = base64.b64encode(os.urandom(32)).decode("utf-8")
        public_key = hashlib.sha256(
            private_key.encode("utf-8")
        ).hexdigest()
        return (public_key, private_key)

    def _record_failure(
        self,
        plugin_id: str,
        failure_type: str,
        details: Dict[str, Any],
    ) -> None:
        """Record a verification failure for audit.

        Args:
            plugin_id: The plugin involved.
            failure_type: The type of failure.
            details: Additional failure details.
        """
        entry: Dict[str, Any] = {
            "plugin_id": plugin_id,
            "failure_type": failure_type,
            "details": details,
            "timestamp": time.time(),
        }
        with self._lock:
            self._failures.append(entry)
            if len(self._failures) > self._max_failures:
                self._failures = self._failures[-self._max_failures:]

    def get_failures(
        self, plugin_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get verification failures, optionally filtered by plugin.

        Args:
            plugin_id: Optional plugin ID filter.

        Returns:
            A list of failure records.
        """
        with self._lock:
            if plugin_id:
                return [
                    f
                    for f in self._failures
                    if f["plugin_id"] == plugin_id
                ]
            return list(self._failures)

    def get_stats(self) -> Dict[str, Any]:
        """Get signature verifier statistics.

        Returns:
            A dictionary with key counts, RSA availability,
            and failure counts.
        """
        with self._lock:
            return {
                "use_rsa": self._use_rsa,
                "registered_keys": len(self._key_cache),
                "plugins": sorted(self._key_cache.keys()),
                "total_failures": len(self._failures),
                "recent_failures": self._failures[-10:],
            }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the verifier state to a dictionary.

        Returns:
            A dictionary with registered keys and configuration.
        """
        with self._lock:
            return {
                "use_rsa": self._use_rsa,
                "keys": {
                    pid: {"public": k[0]}
                    for pid, k in self._key_cache.items()
                },
            }