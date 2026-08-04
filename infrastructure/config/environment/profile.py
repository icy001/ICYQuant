"""
Environment profile definitions.

Defines the standard environment profiles:
base, development, testing, staging, production.

Profile hierarchy:
    base
    ├── development
    ├── testing
    ├── staging
    └── production

Each profile inherits from base and can
override or extend variables.
"""

from __future__ import annotations

from typing import Any, Dict

from .models import EnvironmentProfile


# ── Base Profile ──

BASE_PROFILE = EnvironmentProfile(
    name="base",
    parent=None,
    description="Base configuration shared across all environments",
    variables={
        "app.name": "ICYQuant",
        "app.version": "0.4.0",
        "app.environment": "base",
        # Server
        "server.host": "0.0.0.0",
        "server.port": 8080,
        "server.workers": 4,
        # Database
        "database.host": "localhost",
        "database.port": 5432,
        "database.name": "icyquant",
        "database.pool_size": 10,
        # Redis
        "redis.host": "localhost",
        "redis.port": 6379,
        "redis.db": 0,
        # Kafka
        "kafka.bootstrap_servers": "localhost:9092",
        "kafka.group_id": "icyquant",
        # Logging
        "logging.level": "INFO",
        "logging.format": "json",
        # Metrics
        "metrics.enabled": True,
        "metrics.port": 9090,
    },
    readonly=True,
)


# ── Development Profile ──

DEVELOPMENT_PROFILE = EnvironmentProfile(
    name="development",
    parent="base",
    description="Development environment with verbose logging",
    variables={
        "app.environment": "development",
        "server.debug": True,
        "logging.level": "DEBUG",
        "database.name": "icyquant_dev",
        "database.pool_size": 5,
        "redis.db": 1,
        "server.auto_reload": True,
    },
)


# ── Testing Profile ──

TESTING_PROFILE = EnvironmentProfile(
    name="testing",
    parent="base",
    description="Testing environment with isolated resources",
    variables={
        "app.environment": "testing",
        "server.debug": True,
        "logging.level": "DEBUG",
        "database.name": "icyquant_test",
        "database.pool_size": 3,
        "redis.db": 2,
        "kafka.group_id": "icyquant_test",
    },
)


# ── Staging Profile ──

STAGING_PROFILE = EnvironmentProfile(
    name="staging",
    parent="base",
    description="Staging environment mirroring production",
    variables={
        "app.environment": "staging",
        "server.debug": False,
        "logging.level": "INFO",
        "database.name": "icyquant_staging",
        "database.pool_size": 10,
        "redis.db": 3,
        "kafka.group_id": "icyquant_staging",
    },
)


# ── Production Profile ──

PRODUCTION_PROFILE = EnvironmentProfile(
    name="production",
    parent="base",
    description="Production environment with optimized settings",
    variables={
        "app.environment": "production",
        "server.debug": False,
        "logging.level": "WARNING",
        "database.name": "icyquant_prod",
        "database.pool_size": 50,
        "redis.db": 0,
        "redis.max_connections": 100,
        "kafka.group_id": "icyquant_prod",
        "server.workers": 16,
        "server.graceful_timeout": 30,
    },
)


# ── Profile Registry ──

STANDARD_PROFILES: Dict[str, EnvironmentProfile] = {
    "base": BASE_PROFILE,
    "development": DEVELOPMENT_PROFILE,
    "testing": TESTING_PROFILE,
    "staging": STAGING_PROFILE,
    "production": PRODUCTION_PROFILE,
}


def get_profile(
    name: str,
) -> EnvironmentProfile:
    """Get a standard profile by name."""
    if name not in STANDARD_PROFILES:
        raise ValueError(
            f"Unknown profile: {name}. "
            f"Available: {list(STANDARD_PROFILES.keys())}"
        )
    return STANDARD_PROFILES[name]


def list_profiles(
) -> list:
    """List all standard profile names."""
    return list(STANDARD_PROFILES.keys())


def get_profile_names(
) -> list:
    """Get all profile names."""
    return list(STANDARD_PROFILES.keys())
