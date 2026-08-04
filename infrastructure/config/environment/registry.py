"""
Environment registry.

Manages environment profiles and tracks
the active profile.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from .models import EnvironmentProfile


class EnvironmentRegistry:
    """
    Registry for environment profiles.

    Stores all registered profiles and tracks
    the currently active profile.

    Thread-safe for concurrent access.
    """

    def __init__(
        self,
    ) -> None:
        self._profiles: Dict[str, EnvironmentProfile] = {}
        self._active_profile: Optional[str] = None
        self._lock = threading.RLock()

    @property
    def active_profile(
        self,
    ) -> Optional[str]:
        """Get active profile name."""
        return self._active_profile

    @property
    def profile_count(
        self,
    ) -> int:
        """Get number of registered profiles."""
        with self._lock:
            return len(self._profiles)

    def register(
        self,
        profile: EnvironmentProfile,
    ) -> None:
        """
        Register an environment profile.

        Args:
            profile: EnvironmentProfile to register.
        """
        with self._lock:
            self._profiles[profile.name] = profile

    def register_many(
        self,
        profiles: List[EnvironmentProfile],
    ) -> None:
        """Register multiple profiles."""
        with self._lock:
            for profile in profiles:
                self._profiles[profile.name] = profile

    def get(
        self,
        name: str,
    ) -> Optional[EnvironmentProfile]:
        """
        Get a profile by name.

        Args:
            name: Profile name.

        Returns:
            EnvironmentProfile or None.
        """
        with self._lock:
            return self._profiles.get(name)

    def get_active(
        self,
    ) -> Optional[EnvironmentProfile]:
        """Get the currently active profile."""
        with self._lock:
            if self._active_profile is None:
                return None
            return self._profiles.get(self._active_profile)

    def activate(
        self,
        name: str,
    ) -> EnvironmentProfile:
        """
        Activate a profile.

        Args:
            name: Profile name to activate.

        Returns:
            The activated EnvironmentProfile.

        Raises:
            ValueError: If profile not found.
        """
        with self._lock:
            if name not in self._profiles:
                raise ValueError(
                    f"Profile not found: {name}. "
                    f"Available: {list(self._profiles.keys())}"
                )
            self._active_profile = name
            return self._profiles[name]

    def deactivate(
        self,
    ) -> None:
        """Deactivate the current profile."""
        with self._lock:
            self._active_profile = None

    def list_profiles(
        self,
    ) -> List[str]:
        """List all profile names."""
        with self._lock:
            return list(self._profiles.keys())

    def has_profile(
        self,
        name: str,
    ) -> bool:
        """Check if a profile exists."""
        with self._lock:
            return name in self._profiles

    def get_profile_names(
        self,
    ) -> List[str]:
        """Get all profile names (alias)."""
        return self.list_profiles()
