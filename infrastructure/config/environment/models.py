"""
Environment data models.

Defines the core data structures for
environment profiles and multi-tenant
configuration support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EnvironmentProfile:
    """
    An environment profile definition.

    Profiles define a set of configuration
    variables for a specific environment
    (development, testing, staging, production).

    Supports inheritance through parent profiles.

    Attributes:
        name: Profile name (e.g., "development").
        parent: Parent profile name for inheritance.
        description: Human-readable description.
        variables: Configuration variables for this profile.
        readonly: Whether profile variables are read-only.
    """

    name: str
    parent: Optional[str] = None
    description: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)
    readonly: bool = False

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """Get a variable from this profile."""
        return self.variables.get(key, default)

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "parent": self.parent,
            "description": self.description,
            "variables": dict(self.variables),
            "readonly": self.readonly,
        }


@dataclass
class TenantProfile:
    """
    A tenant profile for multi-tenant support.

    Represents a tenant's configuration
    overlay on top of the global environment.

    Attributes:
        tenant_id: Unique tenant identifier.
        name: Tenant name.
        variables: Tenant-specific variables.
        enabled: Whether this tenant is active.
    """

    tenant_id: str
    name: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """Get a tenant variable."""
        return self.variables.get(key, default)

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "variables": dict(self.variables),
            "enabled": self.enabled,
        }


@dataclass
class OverlayResult:
    """
    Result of applying configuration overlays.

    Contains the final effective configuration
    along with metadata about which profiles
    contributed.

    Attributes:
        effective: The final merged configuration.
        layers: List of (layer_name, variables_dict) tuples.
        active_profile: The active profile name.
        tenant_id: Active tenant ID (if any).
    """

    effective: Dict[str, Any] = field(default_factory=dict)
    layers: List[tuple] = field(default_factory=list)
    active_profile: str = ""
    tenant_id: Optional[str] = None

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """Get an effective configuration value."""
        return self.effective.get(key, default)

    def trace_key(
        self,
        key: str,
    ) -> List[tuple]:
        """
        Trace which layers contributed to a key.

        Returns list of (layer_name, value) for
        each layer that defines this key.
        """
        result = []
        for layer_name, variables in self.layers:
            if key in variables:
                result.append((layer_name, variables[key]))
        return result

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "effective": dict(self.effective),
            "layers": [
                {"layer": name, "keys": list(vars.keys())}
                for name, vars in self.layers
            ],
            "active_profile": self.active_profile,
            "tenant_id": self.tenant_id,
        }
