from infrastructure.config import (
    EnvironmentProfile,
    EnvironmentRegistry,
    ProfileInheritance,
    BASE_PROFILE,
    DEVELOPMENT_PROFILE,
    STANDARD_PROFILES,
    get_profile,
    list_profiles,
)


def test_environment():
    """Test environment profile system."""
    # Profile should exist
    profile = get_profile("production")
    assert profile is not None
    assert profile.name == "production"


def test_profile_listing():
    """Test listing available profiles."""
    profiles = list_profiles()
    assert "base" in profiles
    assert "development" in profiles
    assert "production" in profiles


def test_profile_inheritance():
    """Test profile inheritance."""
    registry = EnvironmentRegistry()
    registry.register_many(list(STANDARD_PROFILES.values()))

    inheritance = ProfileInheritance(registry)
    resolved = inheritance.resolve(DEVELOPMENT_PROFILE)

    # Inherited from base
    assert resolved.get("database.name") == "icyquant_dev"
    # Overridden in development
    assert resolved.get("logging.level") == "DEBUG"
