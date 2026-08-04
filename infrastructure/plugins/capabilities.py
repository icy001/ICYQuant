from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class Capability(Enum):
    MARKET_DATA = "market_data"
    BROKER = "broker"
    EXECUTION = "execution"
    RISK = "risk"
    STRATEGY = "strategy"
    STORAGE = "storage"
    AI = "ai"
    NOTIFICATION = "notification"
    SCHEDULER = "scheduler"
    ANALYTICS = "analytics"
    COMPLIANCE = "compliance"
    REPORTING = "reporting"


@dataclass
class CapabilityRequirement:
    capability: Capability
    min_version: str = "1.0.0"
    required: bool = True
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability": self.capability.value,
            "min_version": self.min_version,
            "required": self.required,
            "config": dict(self.config),
        }


@dataclass
class CapabilityDeclaration:
    plugin_id: str
    capabilities: List[CapabilityRequirement]

    def has_capability(self, cap: Capability) -> bool:
        return any(req.capability == cap for req in self.capabilities)

    def get_required(self) -> List[CapabilityRequirement]:
        return [req for req in self.capabilities if req.required]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "capabilities": [req.to_dict() for req in self.capabilities],
        }

    @classmethod
    def from_dict(cls, plugin_id: str, data: dict) -> CapabilityDeclaration:
        capabilities: List[CapabilityRequirement] = []
        for item in data.get("capabilities", []):
            capabilities.append(
                CapabilityRequirement(
                    capability=Capability(item["capability"]),
                    min_version=item.get("min_version", "1.0.0"),
                    required=item.get("required", True),
                    config=dict(item.get("config", {})),
                )
            )
        return cls(plugin_id=plugin_id, capabilities=capabilities)


class CapabilityRegistry:
    """Tracks which plugins provide which capabilities."""

    def __init__(self) -> None:
        self._plugin_caps: Dict[str, List[Capability]] = {}
        self._cap_plugins: Dict[Capability, List[str]] = {}

    def register(self, plugin_id: str, capabilities: List[Capability]) -> None:
        # Re-registering must replace, not duplicate, existing mappings.
        self.unregister(plugin_id)
        self._plugin_caps[plugin_id] = list(capabilities)
        for cap in capabilities:
            plugins = self._cap_plugins.setdefault(cap, [])
            if plugin_id not in plugins:
                plugins.append(plugin_id)

    def unregister(self, plugin_id: str) -> None:
        caps = self._plugin_caps.pop(plugin_id, [])
        for cap in caps:
            plugins = self._cap_plugins.get(cap, [])
            if plugin_id in plugins:
                plugins.remove(plugin_id)
            if not plugins:
                self._cap_plugins.pop(cap, None)

    def get_plugins_with_capability(self, cap: Capability) -> List[str]:
        return list(self._cap_plugins.get(cap, []))

    def has_capability(self, plugin_id: str, cap: Capability) -> bool:
        return plugin_id in self._cap_plugins.get(cap, [])

    def get_capabilities(self, plugin_id: str) -> List[Capability]:
        return list(self._plugin_caps.get(plugin_id, []))

    def resolve(self, cap: Capability) -> Optional[str]:
        """Return the first plugin that provides the capability."""
        plugins = self._cap_plugins.get(cap, [])
        return plugins[0] if plugins else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_capabilities": {
                pid: [c.value for c in caps]
                for pid, caps in self._plugin_caps.items()
            },
            "capability_plugins": {
                cap.value: list(plugins)
                for cap, plugins in self._cap_plugins.items()
            },
        }
