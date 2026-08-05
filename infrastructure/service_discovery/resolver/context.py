"""Resolution context for service discovery.

Provides ``ResolveContext`` which encapsulates the parameters for
resolving a service instance, including version, region, zone,
strategy, canary flag, features, and timeout.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..instance import ServiceInstance

logger = logging.getLogger(__name__)


class ResolveContext:
    """Context for a service resolution request.

    Encapsulates all parameters that influence service instance
    selection including version, region, zone, strategy, canary
    deployment flag, feature flags, and timeout.

    Args:
        namespace: Namespace to resolve in.
        version: Optional version constraint.
        region: Optional geographic region filter.
        zone: Optional availability zone filter.
        user_id: Optional user identifier for affinity-based routing.
        strategy: Load balancing strategy name.
        canary: Whether to prefer canary instances.
        features: Feature flag mapping for canary/feature-based routing.
        metadata: Additional metadata for context-aware routing.
        timeout: Resolution timeout in seconds.
    """

    __slots__ = (
        "namespace",
        "version",
        "region",
        "zone",
        "user_id",
        "strategy",
        "canary",
        "features",
        "metadata",
        "timeout",
    )

    def __init__(
        self,
        namespace: str = "default",
        version: str = None,
        region: str = None,
        zone: str = None,
        user_id: str = None,
        strategy: str = "round_robin",
        canary: bool = False,
        features: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: float = 5.0,
    ) -> None:
        self.namespace = namespace or "default"
        self.version = version
        self.region = region
        self.zone = zone
        self.user_id = user_id
        self.strategy = strategy or "round_robin"
        self.canary = bool(canary)
        self.features = dict(features) if features else {}
        self.metadata = dict(metadata) if metadata else {}
        self.timeout = float(timeout) if timeout else 5.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the context to a dictionary.

        Returns:
            Dictionary representation of the context.
        """
        return {
            "namespace": self.namespace,
            "version": self.version,
            "region": self.region,
            "zone": self.zone,
            "user_id": self.user_id,
            "strategy": self.strategy,
            "canary": self.canary,
            "features": dict(self.features),
            "metadata": dict(self.metadata),
            "timeout": self.timeout,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ResolveContext:
        """Deserialize a context from a dictionary.

        Args:
            data: Dictionary containing context fields.

        Returns:
            A new ``ResolveContext`` instance.
        """
        if data is None:
            data = {}
        return cls(
            namespace=str(data.get("namespace", "default")),
            version=data.get("version"),
            region=data.get("region"),
            zone=data.get("zone"),
            user_id=data.get("user_id"),
            strategy=str(data.get("strategy", "round_robin")),
            canary=bool(data.get("canary", False)),
            features=dict(data.get("features", {}) or {}),
            metadata=dict(data.get("metadata", {}) or {}),
            timeout=float(data.get("timeout", 5.0)),
        )

    def matches_instance(self, instance: ServiceInstance) -> bool:
        """Check whether a service instance matches this context.

        Validates that the instance satisfies all constraints
        specified in this context, including namespace, version,
        region, zone, canary flag, and feature flags.

        Args:
            instance: The ``ServiceInstance`` to check.

        Returns:
            True if the instance matches all context constraints.
        """
        if instance is None:
            return False
        if instance.namespace != self.namespace:
            return False
        if self.version is not None and instance.version != self.version:
            return False
        if self.region is not None:
            instance_region = ""
            if isinstance(instance.metadata, dict):
                instance_region = str(instance.metadata.get("region", ""))
            if instance_region != self.region:
                return False
        if self.zone is not None:
            instance_zone = ""
            if isinstance(instance.metadata, dict):
                instance_zone = str(instance.metadata.get("zone", ""))
            if instance_zone != self.zone:
                return False
        if self.canary:
            instance_canary = False
            if isinstance(instance.metadata, dict):
                instance_canary = bool(instance.metadata.get("canary", False))
            if not instance_canary:
                return False
        if self.features:
            instance_features = {}
            if isinstance(instance.metadata, dict):
                instance_features = dict(instance.metadata.get("features", {}) or {})
            for feature, value in self.features.items():
                if instance_features.get(feature) != value:
                    return False
        return True

    def with_version(self, version: str) -> ResolveContext:
        """Return a new context with the version constraint set.

        Args:
            version: The version string to set.

        Returns:
            A new ``ResolveContext`` with the version updated.
        """
        return ResolveContext(
            namespace=self.namespace,
            version=version,
            region=self.region,
            zone=self.zone,
            user_id=self.user_id,
            strategy=self.strategy,
            canary=self.canary,
            features=dict(self.features),
            metadata=dict(self.metadata),
            timeout=self.timeout,
        )

    def with_strategy(self, strategy: str) -> ResolveContext:
        """Return a new context with the strategy updated.

        Args:
            strategy: The strategy name to set.

        Returns:
            A new ``ResolveContext`` with the strategy updated.
        """
        return ResolveContext(
            namespace=self.namespace,
            version=self.version,
            region=self.region,
            zone=self.zone,
            user_id=self.user_id,
            strategy=strategy,
            canary=self.canary,
            features=dict(self.features),
            metadata=dict(self.metadata),
            timeout=self.timeout,
        )

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ResolveContext):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return (
            f"ResolveContext(namespace={self.namespace!r}, "
            f"version={self.version!r}, strategy={self.strategy!r}, "
            f"canary={self.canary!r})"
        )