"""Trust domain management for ICYQuant Service Mesh.

Provides ``TrustDomain`` for defining trust boundaries and
controlling cross-domain identity acceptance.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .exceptions import TrustDomainError

logger = logging.getLogger(__name__)


class TrustDomainLevel(str, Enum):
    """Trust domain security level."""

    PRODUCTION = "production"
    STAGING = "staging"
    TESTING = "testing"
    RESEARCH = "research"


class TrustDomain:
    """Represents a trust domain in the mesh."""

    def __init__(
        self,
        name: str = "icyquant.local",
        level: TrustDomainLevel = TrustDomainLevel.PRODUCTION,
        description: str = "",
        allow_cross_domain: bool = False,
        federated_domains: Optional[List[str]] = None,
    ) -> None:
        self.name = name
        self.level = level
        self.description = description
        self.allow_cross_domain = allow_cross_domain
        self.federated_domains = federated_domains or []
        self.created_at = datetime.utcnow()
        self._enabled = True

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def is_federated(self, domain: str) -> bool:
        return domain in self.federated_domains

    def add_federation(self, domain: str) -> None:
        if domain not in self.federated_domains and domain != self.name:
            self.federated_domains.append(domain)

    def remove_federation(self, domain: str) -> bool:
        if domain in self.federated_domains:
            self.federated_domains.remove(domain)
            return True
        return False

    def accepts_identity_from(self, source_domain: str) -> bool:
        """Check if this trust domain accepts identities from source."""
        if source_domain == self.name:
            return True
        if self.allow_cross_domain and self.is_federated(source_domain):
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "level": self.level.value,
            "description": self.description,
            "allow_cross_domain": self.allow_cross_domain,
            "federated_domains": self.federated_domains,
            "enabled": self._enabled,
            "created_at": self.created_at.isoformat(),
        }


class TrustDomainManager:
    """Manages trust domains."""

    def __init__(self, default_domain: Optional[TrustDomain] = None) -> None:
        self._lock = threading.RLock()
        self._domains: Dict[str, TrustDomain] = {}
        if default_domain:
            self.register(default_domain)
        else:
            self.register(TrustDomain())

    def register(self, domain: TrustDomain) -> None:
        with self._lock:
            self._domains[domain.name] = domain
        logger.info("Trust domain registered: %s", domain.name)

    def unregister(self, name: str) -> bool:
        with self._lock:
            if name in self._domains:
                del self._domains[name]
                return True
            return False

    def get_domain(self, name: str) -> Optional[TrustDomain]:
        with self._lock:
            return self._domains.get(name)

    def list_domains(self) -> List[TrustDomain]:
        with self._lock:
            return list(self._domains.values())

    def validate_trust(self, source_domain: str, target_domain: str) -> bool:
        """Validate if source domain is trusted by target domain."""
        target = self.get_domain(target_domain)
        if not target:
            return False
        if not target.is_enabled:
            return False
        return target.accepts_identity_from(source_domain)

    def add_federation(self, domain_a: str, domain_b: str) -> None:
        """Establish bidirectional federation between two domains."""
        a = self.get_domain(domain_a)
        b = self.get_domain(domain_b)
        if not a or not b:
            raise TrustDomainError("Both domains must be registered")
        a.add_federation(domain_b)
        b.add_federation(domain_a)
        logger.info("Federation established: %s <-> %s", domain_a, domain_b)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "domain_count": len(self._domains),
                "enabled_count": sum(1 for d in self._domains.values() if d.is_enabled),
                "federation_count": sum(len(d.federated_domains) for d in self._domains.values()),
            }
