"""Certificate revocation for ICYQuant Service Mesh.

Provides ``RevocationManager`` for managing certificate revocation
lists (CRL) and distributing revocation updates across the mesh.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RevocationReason(str):
    """Revocation reason codes."""

    UNSPECIFIED = "unspecified"
    KEY_COMPROMISE = "key_compromise"
    CA_COMPROMISE = "ca_compromise"
    AFFILIATION_CHANGED = "affiliation_changed"
    SUPERSEDED = "superseded"
    CESSATION_OF_OPERATION = "cessation_of_operation"
    CERTIFICATE_HOLD = "certificate_hold"
    EXPIRED = "expired"
    REMOVED_FROM_CRL = "removed_from_crl"


class RevocationEntry:
    """A revocation list entry."""

    def __init__(
        self,
        cert_id: str,
        serial_number: str = "",
        reason: str = RevocationReason.UNSPECIFIED,
        revoked_by: str = "system",
    ) -> None:
        self.cert_id = cert_id
        self.serial_number = serial_number
        self.reason = reason
        self.revoked_by = revoked_by
        self.revoked_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cert_id": self.cert_id,
            "serial_number": self.serial_number,
            "reason": self.reason,
            "revoked_by": self.revoked_by,
            "revoked_at": self.revoked_at.isoformat(),
        }


class RevocationManager:
    """Manages certificate revocation lists."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._revoked: Dict[str, RevocationEntry] = {}
        self._listeners: List = []
        self._update_count = 0

    def revoke(
        self,
        cert_id: str,
        serial_number: str = "",
        reason: str = RevocationReason.UNSPECIFIED,
        revoked_by: str = "system",
    ) -> RevocationEntry:
        """Add a certificate to the revocation list."""
        entry = RevocationEntry(
            cert_id=cert_id,
            serial_number=serial_number,
            reason=reason,
            revoked_by=revoked_by,
        )
        with self._lock:
            self._revoked[cert_id] = entry
            self._update_count += 1
        self._notify_listeners("revoke", entry.to_dict())
        logger.warning("Certificate revoked: %s (reason: %s)", cert_id, reason)
        return entry

    def unrevoke(self, cert_id: str) -> bool:
        """Remove a certificate from the revocation list."""
        with self._lock:
            if cert_id in self._revoked:
                del self._revoked[cert_id]
                self._update_count += 1
                self._notify_listeners("unrevoke", {"cert_id": cert_id})
                return True
            return False

    def is_revoked(self, cert_id: str) -> bool:
        with self._lock:
            return cert_id in self._revoked

    def is_revoked_by_serial(self, serial_number: str) -> bool:
        with self._lock:
            return any(
                e.serial_number == serial_number
                for e in self._revoked.values()
            )

    def get_revocation_entry(self, cert_id: str) -> Optional[RevocationEntry]:
        with self._lock:
            return self._revoked.get(cert_id)

    def get_revocation_list(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self._revoked.values()]

    def get_crl(self) -> Dict[str, Any]:
        """Get the full CRL (Certificate Revocation List)."""
        with self._lock:
            return {
                "issuer": "icyquant-ca",
                "entries": [e.to_dict() for e in self._revoked.values()],
                "count": len(self._revoked),
                "updated_at": datetime.utcnow().isoformat(),
            }

    def subscribe(self, listener) -> None:
        with self._lock:
            self._listeners.append(listener)

    def _notify_listeners(self, event: str, data: Any) -> None:
        for listener in list(self._listeners):
            try:
                listener(event, data)
            except Exception as exc:
                logger.warning("Revocation listener failed: %s", exc)

    def clear(self) -> None:
        with self._lock:
            self._revoked.clear()
            self._update_count += 1

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "revoked_count": len(self._revoked),
                "update_count": self._update_count,
                "listener_count": len(self._listeners),
            }
