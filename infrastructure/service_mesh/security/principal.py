"""Security principal for ICYQuant Service Mesh.

Provides ``Principal`` for representing authenticated entities
(workloads, services, users) with associated attributes and roles.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Principal:
    """An authenticated principal in the mesh."""

    def __init__(
        self,
        principal_id: str,
        spiffe_id: str = "",
        trust_domain: str = "icyquant.local",
        namespace: str = "default",
        service_name: str = "",
        roles: Optional[List[str]] = None,
        attributes: Optional[Dict[str, str]] = None,
    ) -> None:
        self.principal_id = principal_id
        self.spiffe_id = spiffe_id
        self.trust_domain = trust_domain
        self.namespace = namespace
        self.service_name = service_name
        self.roles = roles or []
        self.attributes = attributes or {}
        self.authenticated = False
        self.authenticated_at: Optional[datetime] = None
        self.auth_method: str = ""

    def add_role(self, role: str) -> None:
        if role not in self.roles:
            self.roles.append(role)

    def remove_role(self, role: str) -> bool:
        if role in self.roles:
            self.roles.remove(role)
            return True
        return False

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_attribute(self, key: str) -> bool:
        return key in self.attributes

    def get_attribute(self, key: str, default: str = "") -> str:
        return self.attributes.get(key, default)

    def set_attribute(self, key: str, value: str) -> None:
        self.attributes[key] = value

    def mark_authenticated(self, method: str = "certificate") -> None:
        self.authenticated = True
        self.authenticated_at = datetime.utcnow()
        self.auth_method = method

    @property
    def is_authenticated(self) -> bool:
        return self.authenticated

    def to_dict(self) -> Dict[str, Any]:
        return {
            "principal_id": self.principal_id,
            "spiffe_id": self.spiffe_id,
            "trust_domain": self.trust_domain,
            "namespace": self.namespace,
            "service_name": self.service_name,
            "roles": self.roles,
            "attributes": self.attributes,
            "authenticated": self.authenticated,
            "authenticated_at": self.authenticated_at.isoformat() if self.authenticated_at else None,
            "auth_method": self.auth_method,
        }

    @classmethod
    def from_spiffe_id(cls, spiffe_id: str) -> "Principal":
        """Create a principal from a SPIFFE ID."""
        parts = spiffe_id.replace("spiffe://", "").split("/")
        trust_domain = parts[0] if parts else "icyquant.local"
        namespace = parts[1] if len(parts) > 1 else "default"
        service_name = parts[2] if len(parts) > 2 else ""
        principal_id = spiffe_id
        return cls(
            principal_id=principal_id,
            spiffe_id=spiffe_id,
            trust_domain=trust_domain,
            namespace=namespace,
            service_name=service_name,
        )

    def __repr__(self) -> str:
        return f"Principal(id={self.principal_id}, spiffe={self.spiffe_id})"


class PrincipalStore:
    """Thread-safe principal store."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._principals: Dict[str, Principal] = {}

    def register(self, principal: Principal) -> None:
        with self._lock:
            self._principals[principal.principal_id] = principal

    def get(self, principal_id: str) -> Optional[Principal]:
        with self._lock:
            return self._principals.get(principal_id)

    def remove(self, principal_id: str) -> bool:
        with self._lock:
            if principal_id in self._principals:
                del self._principals[principal_id]
                return True
            return False

    def list_principals(self) -> List[Principal]:
        with self._lock:
            return list(self._principals.values())

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "principal_count": len(self._principals),
                "authenticated": sum(1 for p in self._principals.values() if p.is_authenticated),
            }
