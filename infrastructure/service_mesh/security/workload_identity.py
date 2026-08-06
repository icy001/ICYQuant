"""Workload identity for ICYQuant Service Mesh.

Provides ``WorkloadIdentity`` for representing service identities
in SPIFFE format: spiffe://trust-domain/namespace/service-name.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .exceptions import WorkloadIdentityError
from .identity import Identity, IdentityService, IdentityStatus

logger = logging.getLogger(__name__)


class WorkloadIdentity:
    """Represents a workload identity in the mesh."""

    def __init__(
        self,
        trust_domain: str = "icyquant.local",
        namespace: str = "default",
        service_name: str = "",
        instance_id: str = "",
        ttl_seconds: int = 3600,
    ) -> None:
        self.trust_domain = trust_domain
        self.namespace = namespace
        self.service_name = service_name
        self.instance_id = instance_id
        self.ttl_seconds = ttl_seconds
        self.created_at = datetime.utcnow()
        self._spiffe_id = self._build_spiffe_id()
        self._identity_id = self._build_identity_id()
        self.expires_at = self.created_at + timedelta(seconds=ttl_seconds)

    def _build_spiffe_id(self) -> str:
        path = f"{self.namespace}/{self.service_name}"
        if self.instance_id:
            path = f"{path}/{self.instance_id}"
        return f"spiffe://{self.trust_domain}/{path}"

    def _build_identity_id(self) -> str:
        raw = f"{self._spiffe_id}:{self.created_at.isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @property
    def spiffe_id(self) -> str:
        return self._spiffe_id

    @property
    def identity_id(self) -> str:
        return self._identity_id

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def to_identity(self) -> Identity:
        """Convert to an Identity object."""
        identity = Identity(
            identity_id=self._identity_id,
            spiffe_id=self._spiffe_id,
            trust_domain=self.trust_domain,
            namespace=self.namespace,
            service_name=self.service_name,
            instance_id=self.instance_id,
            status=IdentityStatus.ACTIVE,
        )
        identity.expires_at = self.expires_at
        return identity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity_id": self._identity_id,
            "spiffe_id": self._spiffe_id,
            "trust_domain": self.trust_domain,
            "namespace": self.namespace,
            "service_name": self.service_name,
            "instance_id": self.instance_id,
            "ttl_seconds": self.ttl_seconds,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_expired": self.is_expired,
        }


class WorkloadIdentityManager:
    """Manages workload identity lifecycle."""

    def __init__(self, identity_service: Optional[IdentityService] = None) -> None:
        self._identity_service = identity_service or IdentityService()
        self._lock = threading.RLock()
        self._workloads: Dict[str, WorkloadIdentity] = {}

    def create_identity(
        self,
        service_name: str,
        namespace: str = "default",
        trust_domain: str = "icyquant.local",
        instance_id: str = "",
        ttl_seconds: int = 3600,
    ) -> WorkloadIdentity:
        """Create a new workload identity."""
        if not service_name:
            raise WorkloadIdentityError("service_name is required")
        wi = WorkloadIdentity(
            trust_domain=trust_domain,
            namespace=namespace,
            service_name=service_name,
            instance_id=instance_id,
            ttl_seconds=ttl_seconds,
        )
        with self._lock:
            self._workloads[wi.identity_id] = wi
        self._identity_service.register(wi.to_identity())
        logger.info("Workload identity created: %s", wi.spiffe_id)
        return wi

    def get_identity(self, identity_id: str) -> Optional[WorkloadIdentity]:
        with self._lock:
            return self._workloads.get(identity_id)

    def get_by_spiffe_id(self, spiffe_id: str) -> Optional[WorkloadIdentity]:
        with self._lock:
            for wi in self._workloads.values():
                if wi.spiffe_id == spiffe_id:
                    return wi
        return None

    def list_identities(self, namespace: Optional[str] = None) -> List[WorkloadIdentity]:
        with self._lock:
            workloads = list(self._workloads.values())
        if namespace:
            workloads = [w for w in workloads if w.namespace == namespace]
        return workloads

    def revoke_identity(self, identity_id: str) -> bool:
        with self._lock:
            wi = self._workloads.pop(identity_id, None)
        if wi:
            self._identity_service.revoke(identity_id)
            logger.info("Workload identity revoked: %s", wi.spiffe_id)
            return True
        return False

    def refresh_identity(self, identity_id: str, ttl_seconds: int = 3600) -> Optional[WorkloadIdentity]:
        """Refresh an identity's TTL."""
        with self._lock:
            wi = self._workloads.get(identity_id)
        if not wi:
            return None
        wi.expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        return wi

    def cleanup_expired(self) -> int:
        """Remove expired identities."""
        removed = 0
        with self._lock:
            expired = [wid for wid, wi in self._workloads.items() if wi.is_expired]
            for wid in expired:
                del self._workloads[wid]
                self._identity_service.unregister(wid)
                removed += 1
        if removed:
            logger.info("Cleaned up %d expired workload identities", removed)
        return removed

    @property
    def identity_service(self) -> IdentityService:
        return self._identity_service

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "workload_count": len(self._workloads),
                "identity_service": self._identity_service.get_stats(),
            }
