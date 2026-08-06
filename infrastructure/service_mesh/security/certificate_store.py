"""Certificate store for ICYQuant Service Mesh.

Provides ``CertificateStore`` for storing and retrieving certificates
with thread-safe operations.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from .certificate_authority import CertificateRecord

logger = logging.getLogger(__name__)


class CertificateStore:
    """Thread-safe certificate storage."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._certificates: Dict[str, CertificateRecord] = {}
        self._spiffe_index: Dict[str, List[str]] = {}

    def store(self, cert: CertificateRecord) -> None:
        with self._lock:
            self._certificates[cert.cert_id] = cert
            if cert.spiffe_id not in self._spiffe_index:
                self._spiffe_index[cert.spiffe_id] = []
            self._spiffe_index[cert.spiffe_id].append(cert.cert_id)

    def get(self, cert_id: str) -> Optional[CertificateRecord]:
        with self._lock:
            return self._certificates.get(cert_id)

    def get_by_spiffe_id(self, spiffe_id: str) -> List[CertificateRecord]:
        with self._lock:
            cert_ids = self._spiffe_index.get(spiffe_id, [])
            return [self._certificates[cid] for cid in cert_ids if cid in self._certificates]

    def remove(self, cert_id: str) -> bool:
        with self._lock:
            cert = self._certificates.pop(cert_id, None)
            if cert:
                cert_ids = self._spiffe_index.get(cert.spiffe_id, [])
                if cert_id in cert_ids:
                    cert_ids.remove(cert_id)
                    if not cert_ids:
                        del self._spiffe_index[cert.spiffe_id]
                return True
            return False

    def list_all(self) -> List[CertificateRecord]:
        with self._lock:
            return list(self._certificates.values())

    def list_active(self) -> List[CertificateRecord]:
        with self._lock:
            return [c for c in self._certificates.values() if c.is_active]

    def clear(self) -> None:
        with self._lock:
            self._certificates.clear()
            self._spiffe_index.clear()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total": len(self._certificates),
                "active": sum(1 for c in self._certificates.values() if c.is_active),
                "revoked": sum(1 for c in self._certificates.values() if c.is_revoked),
                "expired": sum(1 for c in self._certificates.values() if c.is_expired),
                "spiffe_entries": len(self._spiffe_index),
            }
