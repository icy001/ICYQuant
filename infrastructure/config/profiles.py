"""
Profile configuration system.

Provides a high-level interface for managing
environment profiles, including loading,
inheritance resolution, and overlay application.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .environment.models import EnvironmentProfile, OverlayResult, TenantProfile
from .environment.manager import EnvironmentManager


class ProfileConfiguration:
    """
    High-level profile configuration system.

    Wraps EnvironmentManager with a simpler
    API for common profile operations.

    Usage:
        config = ProfileConfiguration()
        config.setup()

        # Get effective config for development
        effective = config.for_environment("development")

        # Get effective config with tenant
        effective = config.for_tenant("tenant-001", profile="production")
    """

    def __init__(
        self,
        manager: Optional[EnvironmentManager] = None,
    ) -> None:
        """
        Initialize profile configuration.

        Args:
            manager: Pre-configured EnvironmentManager.
        """
        self._manager = manager or EnvironmentManager()
        self._initialized = False

    @property
    def manager(
        self,
    ) -> EnvironmentManager:
        """Get environment manager."""
        return self._manager

    def setup(
        self,
    ) -> None:
        """Initialize standard profiles and auto-detect."""
        self._manager.init_standard_profiles()
        self._manager.auto_detect()
        self._initialized = True

    def for_environment(
        self,
        profile_name: str,
        runtime_overrides: Optional[Dict[str, Any]] = None,
    ) -> OverlayResult:
        """
        Get effective configuration for an environment.

        Args:
            profile_name: Profile name.
            runtime_overrides: Optional runtime overrides.

        Returns:
            OverlayResult with effective configuration.
        """
        self._ensure_initialized()
        self._manager.switch(profile_name)
        return self._manager.resolve(
            runtime_overrides=runtime_overrides,
        )

    def for_tenant(
        self,
        tenant_id: str,
        profile_name: Optional[str] = None,
        tenant_variables: Optional[Dict[str, Any]] = None,
        runtime_overrides: Optional[Dict[str, Any]] = None,
    ) -> OverlayResult:
        """
        Get effective configuration for a tenant.

        Args:
            tenant_id: Tenant identifier.
            profile_name: Profile name (uses current if None).
            tenant_variables: Tenant-specific variables.
            runtime_overrides: Optional runtime overrides.

        Returns:
            OverlayResult with effective configuration.
        """
        self._ensure_initialized()

        if profile_name:
            self._manager.switch(profile_name)

        tenant = TenantProfile(
            tenant_id=tenant_id,
            variables=tenant_variables or {},
        )

        return self._manager.resolve(
            tenant=tenant,
            runtime_overrides=runtime_overrides,
        )

    def get_active(
        self,
    ) -> Optional[EnvironmentProfile]:
        """Get active profile."""
        return self._manager.active_profile

    def list_profiles(
        self,
    ) -> List[str]:
        """List all available profiles."""
        self._ensure_initialized()
        return self._manager.list_profiles()

    def validate(
        self,
    ) -> Dict[str, List[str]]:
        """Validate all profiles."""
        self._ensure_initialized()
        return self._manager.validate()

    def _ensure_initialized(
        self,
    ) -> None:
        """Ensure setup() has been called."""
        if not self._initialized:
            self.setup()
