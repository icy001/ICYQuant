"""Contract Registry — manages registration, resolution, and lifecycle of control contracts.

Supports:
  - Register domain contracts by name + version.
  - Resolve a contract handler for a given domain + version.
  - Validate version compatibility.
  - Deprecate old versions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .contracts.control_version import ContractVersion, VersionCompatibility, check_compatibility
from .contracts.contract_errors import ContractVersionError


# ── Registry entry ──

@dataclass
class _RegistryEntry:
    """Internal entry tracking a registered contract version."""

    handler: Callable[..., Any]
    version: ContractVersion
    registered_at: float = field(default_factory=time.time)
    deprecated: bool = False
    deprecated_at: float = 0.0
    deprecation_message: str = ""


# ── Contract Registry ──

@dataclass
class ContractRegistry:
    """Registry for all cross-domain control contracts.

    Each domain (risk, governance, authority, approval, admission)
    can register multiple versions, and the registry resolves
    the best match for a requested version.
    """

    _entries: Dict[str, Dict[str, _RegistryEntry]] = field(default_factory=dict)
    # _entries[domain][version_str] = _RegistryEntry

    # ── Registration ──

    def register(
        self,
        domain: str,
        version: str,
        handler: Callable[..., Any],
    ) -> None:
        """Register a handler for a domain + version combination."""
        if domain not in self._entries:
            self._entries[domain] = {}

        parsed = ContractVersion.parse(version)
        self._entries[domain][str(parsed)] = _RegistryEntry(
            handler=handler,
            version=parsed,
        )

    # ── Resolution ──

    def resolve(
        self,
        domain: str,
        requested_version: str,
    ) -> Callable[..., Any]:
        """Resolve the best matching handler for a domain + version request.

        Resolution rules:
          1. Exact match → return immediately.
          2. Same major, higher minor → return highest compatible version.
          3. Same major, lower minor → return latest but mark as deprecated.
          4. Different major → raise ContractVersionError.

        Returns:
            The handler callable.

        Raises:
            ContractVersionError: If no compatible version exists.
            KeyError: If the domain is not registered at all.
        """
        if domain not in self._entries:
            raise KeyError(f"Domain '{domain}' is not registered in ContractRegistry")

        requested = ContractVersion.parse(requested_version)
        domain_entries = self._entries[domain]

        # Exact match (but skip deprecated unless it's the only one)
        if str(requested) in domain_entries and not domain_entries[str(requested)].deprecated:
            return domain_entries[str(requested)].handler

        # Find best compatible version
        best_entry: Optional[_RegistryEntry] = None
        best_version: Optional[ContractVersion] = None

        for ver_str, entry in domain_entries.items():
            if entry.deprecated:
                continue
            compat = check_compatibility(requested, entry.version)
            if compat == VersionCompatibility.COMPATIBLE:
                if best_version is None or entry.version > best_version:
                    best_version = entry.version
                    best_entry = entry
            elif compat == VersionCompatibility.DEPRECATED:
                if best_version is None or entry.version > best_version:
                    best_version = entry.version
                    best_entry = entry

        if best_entry is not None:
            return best_entry.handler

        # No compatible version found
        available = list(domain_entries.keys())
        raise ContractVersionError(
            message=f"No compatible version for '{domain}' contract: "
                    f"requested {requested}, available {available}",
            requested_version=requested_version,
            supported_versions=available,
        )

    def resolve_version(
        self,
        domain: str,
        requested_version: str,
    ) -> Tuple[Callable[..., Any], ContractVersion, VersionCompatibility]:
        """Resolve and also return the matched version + compatibility level."""
        if domain not in self._entries:
            raise KeyError(f"Domain '{domain}' is not registered in ContractRegistry")

        requested = ContractVersion.parse(requested_version)
        domain_entries = self._entries[domain]

        # Exact match
        if str(requested) in domain_entries:
            entry = domain_entries[str(requested)]
            return entry.handler, entry.version, VersionCompatibility.COMPATIBLE

        # Find best
        best_entry = None
        best_compat = VersionCompatibility.INCOMPATIBLE
        for ver_str, entry in domain_entries.items():
            compat = check_compatibility(requested, entry.version)
            if compat == VersionCompatibility.COMPATIBLE:
                if best_entry is None or entry.version > best_entry.version:
                    best_entry = entry
                    best_compat = compat
            elif compat == VersionCompatibility.DEPRECATED and best_compat != VersionCompatibility.COMPATIBLE:
                if best_entry is None or entry.version > best_entry.version:
                    best_entry = entry
                    best_compat = compat

        if best_entry is not None:
            return best_entry.handler, best_entry.version, best_compat

        available = list(domain_entries.keys())
        raise ContractVersionError(
            message=f"No compatible version for '{domain}' contract",
            requested_version=requested_version,
            supported_versions=available,
        )

    # ── Version queries ──

    def get_versions(self, domain: str) -> List[str]:
        """Return all registered version strings for a domain."""
        if domain not in self._entries:
            return []
        return sorted(self._entries[domain].keys(), key=lambda v: ContractVersion.parse(v))

    def get_latest_version(self, domain: str) -> Optional[str]:
        versions = self.get_versions(domain)
        return versions[-1] if versions else None

    def is_registered(self, domain: str, version: str) -> bool:
        if domain not in self._entries:
            return False
        return version in self._entries[domain]

    # ── Deprecation ──

    def deprecate(
        self,
        domain: str,
        version: str,
        message: str = "",
    ) -> None:
        """Mark a contract version as deprecated."""
        if domain not in self._entries:
            raise KeyError(f"Domain '{domain}' is not registered")
        if version not in self._entries[domain]:
            raise KeyError(f"Version '{version}' not registered for domain '{domain}'")

        entry = self._entries[domain][version]
        entry.deprecated = True
        entry.deprecated_at = time.time()
        entry.deprecation_message = message

    # ── Lifecycle ──

    def unregister(self, domain: str, version: str) -> None:
        """Remove a contract version from the registry."""
        if domain in self._entries:
            self._entries[domain].pop(version, None)
            if not self._entries[domain]:
                del self._entries[domain]

    def domain_count(self) -> int:
        return len(self._entries)

    def total_versions(self) -> int:
        return sum(len(v) for v in self._entries.values())

    def reset(self) -> None:
        self._entries.clear()

    # ── Serialization ──

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for domain, versions in self._entries.items():
            result[domain] = {}
            for ver_str, entry in versions.items():
                result[domain][ver_str] = {
                    "version": str(entry.version),
                    "registered_at": entry.registered_at,
                    "deprecated": entry.deprecated,
                    "deprecated_at": entry.deprecated_at,
                    "deprecation_message": entry.deprecation_message,
                }
        return result

    def __repr__(self) -> str:
        return f"ContractRegistry(domains={list(self._entries.keys())}, total_versions={self.total_versions()})"
