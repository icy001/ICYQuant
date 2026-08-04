"""
Environment manager.

The unified entry point for environment management,
coordinating detection, profile resolution, and
overlay application.

Runtime Flow:

    EnvironmentDetector
          |
          v
    ProfileLoader / Registry
          |
          v
    ProfileInheritance
          |
          v
    ConfigurationOverlay
          |
          v
    Effective Configuration
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .detector import EnvironmentDetector
from .inheritance import ProfileInheritance
from .loader import ProfileLoader
from .models import EnvironmentProfile, OverlayResult, TenantProfile
from .overlay import ConfigurationOverlay
from .registry import EnvironmentRegistry
from .validator import EnvironmentValidator


class EnvironmentManager:
    """
    Unified environment manager.

    Coordinates all environment management
    components and provides a single entry point
    for environment detection, profile switching,
    and configuration overlay.

    Usage:
        manager = EnvironmentManager()
        manager.init_standard_profiles()

        # Auto-detect and activate
        env_name = manager.auto_detect()
        effective = manager.resolve()

        # Switch profile
        manager.switch("production")
        effective = manager.resolve()
    """

    def __init__(
        self,
        registry: Optional[EnvironmentRegistry] = None,
        detector: Optional[EnvironmentDetector] = None,
    ) -> None:
        """
        Initialize environment manager.

        Args:
            registry: Pre-configured registry.
            detector: Pre-configured detector.
        """
        self._registry = registry or EnvironmentRegistry()
        self._detector = detector or EnvironmentDetector()
        self._loader = ProfileLoader()
        self._inheritance = ProfileInheritance(self._registry)
        self._overlay = ConfigurationOverlay(self._inheritance)
        self._validator = EnvironmentValidator()

    # ── Properties ──

    @property
    def registry(
        self,
    ) -> EnvironmentRegistry:
        """Get environment registry."""
        return self._registry

    @property
    def detector(
        self,
    ) -> EnvironmentDetector:
        """Get environment detector."""
        return self._detector

    @property
    def overlay(
        self,
    ) -> ConfigurationOverlay:
        """Get configuration overlay."""
        return self._overlay

    @property
    def validator(
        self,
    ) -> EnvironmentValidator:
        """Get environment validator."""
        return self._validator

    @property
    def active_profile(
        self,
    ) -> Optional[EnvironmentProfile]:
        """Get active profile."""
        return self._registry.get_active()

    @property
    def active_profile_name(
        self,
    ) -> Optional[str]:
        """Get active profile name."""
        return self._registry.active_profile

    # ── Initialization ──

    def init_standard_profiles(
        self,
    ) -> None:
        """Register all standard profiles."""
        profiles = self._loader.load_all_standard()
        self._registry.register_many(profiles)

    # ── Detection ──

    def auto_detect(
        self,
    ) -> str:
        """
        Auto-detect and activate the environment.

        Returns:
            Detected environment name.
        """
        env_name = self._detector.detect()
        if self._registry.has_profile(env_name):
            self._registry.activate(env_name)
        return env_name

    def detect(
        self,
    ) -> str:
        """Detect environment without activating."""
        return self._detector.detect()

    # ── Profile Management ──

    def switch(
        self,
        profile_name: str,
    ) -> EnvironmentProfile:
        """
        Switch to a different profile.

        Args:
            profile_name: Profile name to activate.

        Returns:
            Activated profile.
        """
        return self._registry.activate(profile_name)

    def current(
        self,
    ) -> Optional[EnvironmentProfile]:
        """Get the current active profile."""
        return self._registry.get_active()

    def register_profile(
        self,
        profile: EnvironmentProfile,
    ) -> None:
        """Register a custom profile."""
        self._registry.register(profile)

    def list_profiles(
        self,
    ) -> List[str]:
        """List all profile names."""
        return self._registry.list_profiles()

    # ── Resolution ──

    def resolve(
        self,
        tenant: Optional[TenantProfile] = None,
        runtime_overrides: Optional[Dict[str, Any]] = None,
    ) -> OverlayResult:
        """
        Resolve the effective configuration.

        Applies the full overlay chain for the
        currently active profile.

        Args:
            tenant: Optional tenant profile.
            runtime_overrides: Optional runtime overrides.

        Returns:
            OverlayResult with effective configuration.
        """
        profile = self._registry.get_active()
        if profile is None:
            raise RuntimeError("No active environment profile")

        return self._overlay.apply(
            profile=profile,
            tenant=tenant,
            runtime_overrides=runtime_overrides,
        )

    def resolve_variables(
        self,
    ) -> Dict[str, Any]:
        """
        Resolve just the inherited variables.

        Returns:
            Dict of resolved variables.
        """
        profile = self._registry.get_active()
        if profile is None:
            return {}
        return self._inheritance.resolve(profile)

    # ── Runtime Overrides ──

    def set_runtime_override(
        self,
        key: str,
        value: Any,
    ) -> None:
        """Set a runtime override."""
        self._overlay.set_runtime_override(key, value)

    def clear_runtime_overrides(
        self,
    ) -> None:
        """Clear all runtime overrides."""
        self._overlay.clear_runtime_overrides()

    # ── Validation ──

    def validate(
        self,
    ) -> Dict[str, List[str]]:
        """
        Validate all registered profiles.

        Returns:
            Dict mapping profile name to errors.
        """
        profiles = [
            self._registry.get(name)
            for name in self._registry.list_profiles()
        ]
        return self._validator.validate_all(profiles, self._registry)

    # ── Status ──

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """Get environment manager status."""
        return {
            "active_profile": self._registry.active_profile,
            "profiles": self._registry.list_profiles(),
            "profile_count": self._registry.profile_count,
            "runtime_overrides": self._overlay.get_runtime_overrides(),
        }
