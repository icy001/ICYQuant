"""
Configuration overlay.

Implements multi-layer configuration overlay
for environments, tenants, and runtime overrides.

Overlay layers (bottom to top):
    Base (lowest priority)
        ↓
    Environment Profile
        ↓
    Tenant Override
        ↓
    Runtime Override (highest priority)

The final effective configuration is produced
by merging all layers, with higher layers
overriding lower ones.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .inheritance import ProfileInheritance
from .models import EnvironmentProfile, OverlayResult, TenantProfile


class ConfigurationOverlay:
    """
    Multi-layer configuration overlay engine.

    Produces the final effective configuration
    by stacking multiple layers:

    1. Base profile variables
    2. Environment profile variables
    3. Tenant-specific overrides
    4. Runtime overrides

    Each layer overrides the previous one.
    """

    def __init__(
        self,
        inheritance: Optional[ProfileInheritance] = None,
    ) -> None:
        """
        Initialize overlay engine.

        Args:
            inheritance: ProfileInheritance instance.
        """
        self._inheritance = inheritance or ProfileInheritance()
        self._runtime_overrides: Dict[str, Any] = {}
        self._tenant_overrides: Dict[str, Dict[str, Any]] = {}

    def apply(
        self,
        profile: EnvironmentProfile,
        tenant: Optional[TenantProfile] = None,
        runtime_overrides: Optional[Dict[str, Any]] = None,
    ) -> OverlayResult:
        """
        Apply configuration overlay for a profile.

        Args:
            profile: Active environment profile.
            tenant: Optional tenant profile.
            runtime_overrides: Optional runtime overrides.

        Returns:
            OverlayResult with effective configuration.
        """
        layers: List[tuple] = []

        # Layer 1: Resolve inherited profile variables
        inherited_vars = self._inheritance.resolve(profile)
        layers.append((f"profile:{profile.name}", inherited_vars))

        effective = dict(inherited_vars)

        # Layer 2: Tenant overrides
        if tenant is not None:
            tenant_vars = tenant.variables
            layers.append((f"tenant:{tenant.tenant_id}", tenant_vars))
            effective = self._merge(effective, tenant_vars)

        # Layer 3: Runtime overrides
        final_overrides = dict(self._runtime_overrides)
        if runtime_overrides:
            final_overrides.update(runtime_overrides)
        if final_overrides:
            layers.append(("runtime", final_overrides))
            effective = self._merge(effective, final_overrides)

        return OverlayResult(
            effective=effective,
            layers=layers,
            active_profile=profile.name,
            tenant_id=tenant.tenant_id if tenant else None,
        )

    def set_runtime_override(
        self,
        key: str,
        value: Any,
    ) -> None:
        """
        Set a runtime override.

        Runtime overrides have the highest priority
        and will be applied on top of all other layers.

        Args:
            key: Configuration key.
            value: Override value.
        """
        self._runtime_overrides[key] = value

    def set_runtime_overrides(
        self,
        overrides: Dict[str, Any],
    ) -> None:
        """Set multiple runtime overrides."""
        self._runtime_overrides.update(overrides)

    def clear_runtime_overrides(
        self,
    ) -> None:
        """Clear all runtime overrides."""
        self._runtime_overrides.clear()

    def get_runtime_overrides(
        self,
    ) -> Dict[str, Any]:
        """Get current runtime overrides."""
        return dict(self._runtime_overrides)

    def set_tenant_override(
        self,
        tenant_id: str,
        key: str,
        value: Any,
    ) -> None:
        """Set a tenant-level override."""
        if tenant_id not in self._tenant_overrides:
            self._tenant_overrides[tenant_id] = {}
        self._tenant_overrides[tenant_id][key] = value

    def clear_tenant_overrides(
        self,
        tenant_id: Optional[str] = None,
    ) -> None:
        """Clear tenant overrides."""
        if tenant_id is None:
            self._tenant_overrides.clear()
        elif tenant_id in self._tenant_overrides:
            del self._tenant_overrides[tenant_id]

    def _merge(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Merge two dictionaries (recursive).

        Nested dicts are merged, other values
        are overridden.
        """
        result = dict(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge(result[key], value)
            else:
                result[key] = value
        return result
