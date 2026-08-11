"""
Strategy manifest definition.

The manifest is the declarative specification of a strategy package,
including metadata, dependencies, entry points, and configuration schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .strategy_metadata import StrategyCapability


@dataclass
class StrategyDependency:
    """A runtime dependency for a strategy."""

    name: str
    version_spec: str = "*"
    """Version constraint (e.g. >=1.0.0, ~=2.1)."""

    optional: bool = False
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version_spec": self.version_spec,
            "optional": self.optional,
            "reason": self.reason,
        }


@dataclass
class StrategyEntryPoint:
    """Entry point definition for a strategy."""

    module: str
    attr: str = "main"
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module": self.module,
            "attr": self.attr,
            "label": self.label,
        }


@dataclass
class StrategyResourceRequirement:
    """Resource requirements for a strategy deployment."""

    cpu_cores: float = 1.0
    memory_mb: int = 512
    disk_mb: int = 1024
    network_access: bool = False
    max_concurrent_executions: int = 1
    timeout_seconds: int = 300

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "disk_mb": self.disk_mb,
            "network_access": self.network_access,
            "max_concurrent_executions": self.max_concurrent_executions,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class StrategyManifest:
    """Declarative manifest for a strategy package."""

    name: str
    version: str
    description: str = ""
    author: str = "unknown"
    license: str = "proprietary"
    capability: StrategyCapability = field(default_factory=StrategyCapability)
    entry_point: StrategyEntryPoint = field(default_factory=StrategyEntryPoint)
    dependencies: List[StrategyDependency] = field(default_factory=list)
    resources: StrategyResourceRequirement = field(default_factory=StrategyResourceRequirement)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    """JSON Schema for strategy configuration."""

    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    documentation_url: str = ""
    repository_url: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    custom_metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StrategyManifest:
        """Create a StrategyManifest from a dictionary."""
        capability_data = data.get("capability", {})
        capability = StrategyCapability(
            asset_classes=capability_data.get("asset_classes", []),
            markets=capability_data.get("markets", []),
            frequency=capability_data.get("frequency", "daily"),
            style=capability_data.get("style", "unknown"),
            long_only=capability_data.get("long_only", True),
            multi_instrument=capability_data.get("multi_instrument", False),
            supports_partial_execution=capability_data.get("supports_partial_execution", False),
        )

        entry_data = data.get("entry_point", {})
        entry_point = StrategyEntryPoint(
            module=entry_data.get("module", ""),
            attr=entry_data.get("attr", "main"),
            label=entry_data.get("label", ""),
        )

        resource_data = data.get("resources", {})
        resources = StrategyResourceRequirement(
            cpu_cores=resource_data.get("cpu_cores", 1.0),
            memory_mb=resource_data.get("memory_mb", 512),
            disk_mb=resource_data.get("disk_mb", 1024),
            network_access=resource_data.get("network_access", False),
            max_concurrent_executions=resource_data.get("max_concurrent_executions", 1),
            timeout_seconds=resource_data.get("timeout_seconds", 300),
        )

        dependencies = [
            StrategyDependency(
                name=d.get("name", ""),
                version_spec=d.get("version_spec", "*"),
                optional=d.get("optional", False),
                reason=d.get("reason", ""),
            )
            for d in data.get("dependencies", [])
        ]

        return cls(
            name=data.get("name", ""),
            version=data.get("version", "0.1.0"),
            description=data.get("description", ""),
            author=data.get("author", "unknown"),
            license=data.get("license", "proprietary"),
            capability=capability,
            entry_point=entry_point,
            dependencies=dependencies,
            resources=resources,
            config_schema=data.get("config_schema", {}),
            tags=data.get("tags", []),
            keywords=data.get("keywords", []),
            documentation_url=data.get("documentation_url", ""),
            repository_url=data.get("repository_url", ""),
            custom_metadata=data.get("custom_metadata", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "capability": self.capability.to_dict(),
            "entry_point": self.entry_point.to_dict(),
            "dependencies": [d.to_dict() for d in self.dependencies],
            "resources": self.resources.to_dict(),
            "config_schema": self.config_schema,
            "tags": self.tags,
            "keywords": self.keywords,
            "documentation_url": self.documentation_url,
            "repository_url": self.repository_url,
            "created_at": self.created_at.isoformat(),
            "custom_metadata": self.custom_metadata,
        }

    def validate_required_fields(self) -> List[str]:
        """Validate that required fields are present. Returns list of missing fields."""
        missing = []
        if not self.name:
            missing.append("name")
        if not self.version:
            missing.append("version")
        if not self.entry_point.module:
            missing.append("entry_point.module")
        return missing
