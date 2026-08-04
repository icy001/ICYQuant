"""
Environment management module.

Provides the environment management framework
including profile definitions, detection,
inheritance, overlay, and validation.
"""

from .models import EnvironmentProfile, OverlayResult, TenantProfile
from .profile import (
    BASE_PROFILE,
    DEVELOPMENT_PROFILE,
    PRODUCTION_PROFILE,
    STAGING_PROFILE,
    STANDARD_PROFILES,
    TESTING_PROFILE,
    get_profile,
    list_profiles,
)
from .registry import EnvironmentRegistry
from .detector import EnvironmentDetector
from .inheritance import ProfileInheritance
from .overlay import ConfigurationOverlay
from .loader import ProfileLoader
from .validator import EnvironmentValidator
from .manager import EnvironmentManager

__all__ = [
    "EnvironmentProfile",
    "TenantProfile",
    "OverlayResult",
    "BASE_PROFILE",
    "DEVELOPMENT_PROFILE",
    "TESTING_PROFILE",
    "STAGING_PROFILE",
    "PRODUCTION_PROFILE",
    "STANDARD_PROFILES",
    "get_profile",
    "list_profiles",
    "EnvironmentRegistry",
    "EnvironmentDetector",
    "ProfileInheritance",
    "ConfigurationOverlay",
    "ProfileLoader",
    "EnvironmentValidator",
    "EnvironmentManager",
]
