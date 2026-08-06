"""Identity models for ICYQuant Service Mesh Security.

Provides ``Identity`` as the base identity model and ``IdentityService``
for managing workload identities within the mesh.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .exceptions import IdentityError

logger = logging.getLogger(__name__)


class IdentityStatus(str, Enum):
    """Status of an identity."""

    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


class Identity:
    """A mesh identity for a workload or service."""

    def __init__(
        self,
        identity_id: str,
        spiffe_id: str,
        trust_domain: str = "icyquant.local",
        namespace: str = "default",
        service_name: str = "",
        instance_id: str = "",
        status: IdentityStatus = IdentityStatus.PENDING,
        attributes: Optional[Dict[str, str]] = None,
    ) -> None:
        self.identity_id = identity_id
        self.spiffe_id = spiffe_id
        self.trust_domain = trust_domain
        self.namespace = namespace
        self.service_name = service_name
        self.instance_id = instance_id
        self.status = status
        self.attributes = attributes or {}
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.expires_at: Optional[datetime] = None

    @property
    def is_active(self) -> bool:
        return self.status == IdentityStatus.ACTIVE

    @property
    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity_id": self.identity_id,
            "spiffe_id": self.spiffe_id,
            "trust_domain": self.trust_domain,
            "namespace": self.namespace,
            "service_name": self.service_name,
            "instance_id": self.instance_id,
            "status": self.status.value,
            "attributes": self.attributes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class IdentityService:
    """Manages workload identities."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._identities: Dict[str, Identity] = {}
        self._spiffe_index: Dict[str, str] = {}
        self._create_count = 0
        self._revoke_count = 0

    def register(self, identity: Identity) -> None:
        with self._lock:
            self._identities[identity.identity_id] = identity
            self._spiffe_index[identity.spiffe_id] = identity.identity_id
            self._create_count += 1
        logger.info("Identity registered: %s", identity.spiffe_id)

    def unregister(self, identity_id: str) -> bool:
        with self._lock:
            identity = self._identities.pop(identity_id, None)
            if identity:
                self._spiffe_index.pop(identity.spiffe_id, None)
                self._revoke_count += 1
                return True
            return False

    def get_identity(self, identity_id: str) -> Optional[Identity]:
        with self._lock:
            return self._identities.get(identity_id)

    def get_by_spiffe_id(self, spiffe_id: str) -> Optional[Identity]:
        with self._lock:
            identity_id = self._spiffe_index.get(spiffe_id)
            if identity_id:
                return self._identities.get(identity_id)
            return None

    def list_identities(self, namespace: Optional[str] = None) -> List[Identity]:
        with self._lock:
            identities = list(self._identities.values())
        if namespace:
            identities = [i for i in identities if i.namespace == namespace]
        return identities

    def activate(self, identity_id: str) -> bool:
        with self._lock:
            identity = self._identities.get(identity_id)
            if identity:
                identity.status = IdentityStatus.ACTIVE
                identity.updated_at = datetime.utcnow()
                return True
            return False

    def suspend(self, identity_id: str) -> bool:
        with self._lock:
            identity = self._identities.get(identity_id)
            if identity:
                identity.status = IdentityStatus.SUSPENDED
                identity.updated_at = datetime.utcnow()
                return True
            return False

    def revoke(self, identity_id: str) -> bool:
        with self._lock:
            identity = self._identities.get(identity_id)
            if identity:
                identity.status = IdentityStatus.REVOKED
                identity.updated_at = datetime.utcnow()
                self._revoke_count += 1
                return True
            return False

    def validate_identity(self, spiffe_id: str) -> bool:
        identity = self.get_by_spiffe_id(spiffe_id)
        if not identity:
            return False
        return identity.is_valid

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            active_count = sum(1 for i in self._identities.values() if i.is_active)
            return {
                "total_identities": len(self._identities),
                "active_identities": active_count,
                "create_count": self._create_count,
                "revoke_count": self._revoke_count,
            }
