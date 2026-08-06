"""SPIFFE identity support for ICYQuant Service Mesh.

Provides SPIFFE-style identity parsing, validation, and bundle
management following the SPIFFE specification.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .exceptions import SPIFFEError

logger = logging.getLogger(__name__)

SPIFFE_PREFIX = "spiffe://"
SPIFFE_REGEX = re.compile(r"^spiffe://([a-zA-Z0-9._-]+)/(.+)$")


class SPIFFEID:
    """Represents a SPIFFE ID."""

    def __init__(self, trust_domain: str, path: str) -> None:
        self.trust_domain = trust_domain
        self.path = path if path.startswith("/") else f"/{path}"

    @property
    def uri(self) -> str:
        return f"{SPIFFE_PREFIX}{self.trust_domain}{self.path}"

    def __str__(self) -> str:
        return self.uri

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, SPIFFEID):
            return self.uri == other.uri
        if isinstance(other, str):
            return self.uri == other
        return False

    def __hash__(self) -> int:
        return hash(self.uri)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trust_domain": self.trust_domain,
            "path": self.path,
            "uri": self.uri,
        }

    @classmethod
    def parse(cls, uri: str) -> "SPIFFEID":
        """Parse a SPIFFE URI string."""
        match = SPIFFE_REGEX.match(uri)
        if not match:
            raise SPIFFEError(f"Invalid SPIFFE ID: {uri}")
        trust_domain = match.group(1)
        path = f"/{match.group(2)}"
        return cls(trust_domain, path)

    @classmethod
    def build(
        cls,
        trust_domain: str,
        namespace: str = "default",
        service: str = "",
        instance: str = "",
    ) -> "SPIFFEID":
        """Build a SPIFFE ID from components."""
        parts = [namespace]
        if service:
            parts.append(service)
        if instance:
            parts.append(instance)
        path = "/".join(parts)
        return cls(trust_domain, path)


class SPIFFEBundle:
    """A SPIFFE Bundle containing trust anchors for a domain."""

    def __init__(self, trust_domain: str) -> None:
        self.trust_domain = trust_domain
        self._keys: Dict[str, str] = {}
        self._lock = threading.RLock()
        self.updated_at = datetime.utcnow()

    def add_key(self, key_id: str, public_key: str) -> None:
        with self._lock:
            self._keys[key_id] = public_key
            self.updated_at = datetime.utcnow()

    def remove_key(self, key_id: str) -> bool:
        with self._lock:
            if key_id in self._keys:
                del self._keys[key_id]
                self.updated_at = datetime.utcnow()
                return True
            return False

    def get_key(self, key_id: str) -> Optional[str]:
        with self._lock:
            return self._keys.get(key_id)

    def list_keys(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._keys)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "trust_domain": self.trust_domain,
                "key_count": len(self._keys),
                "keys": list(self._keys.keys()),
                "updated_at": self.updated_at.isoformat(),
            }


class SPIFFEManager:
    """Manages SPIFFE identities and bundles."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._bundles: Dict[str, SPIFFEBundle] = {}
        self._id_count = 0
        self._validation_count = 0

    def create_id(
        self,
        trust_domain: str,
        namespace: str = "default",
        service: str = "",
        instance: str = "",
    ) -> SPIFFEID:
        """Create a new SPIFFE ID."""
        spiffe_id = SPIFFEID.build(trust_domain, namespace, service, instance)
        with self._lock:
            self._id_count += 1
        return spiffe_id

    def parse_id(self, uri: str) -> SPIFFEID:
        """Parse and validate a SPIFFE URI."""
        return SPIFFEID.parse(uri)

    def validate_id(self, uri: str) -> bool:
        """Validate a SPIFFE ID format."""
        try:
            self.parse_id(uri)
            with self._lock:
                self._validation_count += 1
            return True
        except SPIFFEError:
            return False

    def register_bundle(self, bundle: SPIFFEBundle) -> None:
        with self._lock:
            self._bundles[bundle.trust_domain] = bundle

    def get_bundle(self, trust_domain: str) -> Optional[SPIFFEBundle]:
        with self._lock:
            return self._bundles.get(trust_domain)

    def verify_trust(self, spiffe_id: SPIFFEID) -> bool:
        """Verify that a SPIFFE ID's trust domain has a registered bundle."""
        with self._lock:
            return spiffe_id.trust_domain in self._bundles

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "id_count": self._id_count,
                "validation_count": self._validation_count,
                "bundle_count": len(self._bundles),
            }
