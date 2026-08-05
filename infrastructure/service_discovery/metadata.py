"""Service metadata representation.

Provides a rich ``ServiceMetadata`` class with filtering, capability
checks, and serialization support for the ICYQuant service discovery
module.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .models import ServiceProtocol

logger = logging.getLogger(__name__)


class ServiceMetadata:
    """Metadata describing a service's deployment attributes.

    Args:
        environment: Deployment environment (e.g. production, staging).
        region: Geographic region identifier.
        zone: Availability zone identifier.
        weight: Load balancing weight.
        protocol: Default protocol for the service.
        capabilities: List of capability identifiers.
        tags: List of free-form tags.
        labels: Key/value labels for filtering.
    """

    __slots__ = (
        "environment",
        "region",
        "zone",
        "weight",
        "protocol",
        "capabilities",
        "tags",
        "labels",
    )

    def __init__(
        self,
        environment: str = "",
        region: str = "",
        zone: str = "",
        weight: int = 1,
        protocol: str = "http",
        capabilities: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        self.environment = environment or ""
        self.region = region or ""
        self.zone = zone or ""
        self.weight = int(weight) if weight else 1
        self.protocol = protocol or "http"
        self.capabilities = list(capabilities) if capabilities else []
        self.tags = list(tags) if tags else []
        self.labels = dict(labels) if labels else {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the metadata to a dictionary.

        Returns:
            Dictionary representation of the metadata.
        """
        return {
            "environment": self.environment,
            "region": self.region,
            "zone": self.zone,
            "weight": self.weight,
            "protocol": self.protocol,
            "capabilities": list(self.capabilities),
            "tags": list(self.tags),
            "labels": dict(self.labels),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ServiceMetadata:
        """Deserialize metadata from a dictionary.

        Args:
            data: Dictionary containing metadata fields.

        Returns:
            A new ``ServiceMetadata`` instance.
        """
        if data is None:
            data = {}
        return cls(
            environment=str(data.get("environment", "")),
            region=str(data.get("region", "")),
            zone=str(data.get("zone", "")),
            weight=int(data.get("weight", 1)),
            protocol=str(data.get("protocol", "http")),
            capabilities=list(data.get("capabilities", []) or []),
            tags=list(data.get("tags", []) or []),
            labels=dict(data.get("labels", {}) or {}),
        )

    def has_capability(self, capability: str) -> bool:
        """Check whether the metadata declares a capability.

        Args:
            capability: The capability identifier to check.

        Returns:
            True if the capability is present, False otherwise.
        """
        return capability in self.capabilities

    def has_tag(self, tag: str) -> bool:
        """Check whether the metadata has a tag.

        Args:
            tag: The tag to check.

        Returns:
            True if the tag is present, False otherwise.
        """
        return tag in self.tags

    def get_label(self, key: str, default: Any = None) -> Any:
        """Get a label value by key.

        Args:
            key: The label key.
            default: Value to return if the key is absent.

        Returns:
            The label value or the default.
        """
        return self.labels.get(key, default)

    def matches(self, filter: Dict[str, Any]) -> bool:
        """Check whether the metadata matches a filter.

        The filter supports the following keys:
        - ``environment``: must equal the metadata environment.
        - ``region``: must equal the metadata region.
        - ``zone``: must equal the metadata zone.
        - ``protocol``: must equal the metadata protocol.
        - ``capability``: must be present in capabilities.
        - ``tag``: must be present in tags.
        - ``label``: a dict of key/value pairs that must all match.

        Args:
            filter: Filter criteria mapping.

        Returns:
            True if the metadata matches all filter criteria.
        """
        if not filter:
            return True

        if "environment" in filter and self.environment != filter["environment"]:
            return False
        if "region" in filter and self.region != filter["region"]:
            return False
        if "zone" in filter and self.zone != filter["zone"]:
            return False
        if "protocol" in filter and self.protocol != filter["protocol"]:
            return False
        if "capability" in filter and filter["capability"] not in self.capabilities:
            return False
        if "tag" in filter and filter["tag"] not in self.tags:
            return False

        label_filter = filter.get("label")
        if label_filter:
            if not isinstance(label_filter, dict):
                return False
            for key, value in label_filter.items():
                if self.labels.get(key) != value:
                    return False

        capabilities_filter = filter.get("capabilities")
        if capabilities_filter:
            required = set(capabilities_filter)
            if not required.issubset(set(self.capabilities)):
                return False

        tags_filter = filter.get("tags")
        if tags_filter:
            required_tags = set(tags_filter)
            if not required_tags.issubset(set(self.tags)):
                return False

        return True

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ServiceMetadata):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __hash__(self) -> int:
        return hash(
            (
                self.environment,
                self.region,
                self.zone,
                self.weight,
                self.protocol,
                tuple(self.capabilities),
                tuple(self.tags),
            )
        )

    def __repr__(self) -> str:
        return (
            f"ServiceMetadata(environment={self.environment!r}, "
            f"region={self.region!r}, zone={self.zone!r})"
        )
