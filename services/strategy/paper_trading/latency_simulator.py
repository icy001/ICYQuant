"""
Latency Simulator
=================
Simulates order execution latency with configurable profiles.

Profiles:
    zero   — No latency (ideal)
    low    — 1-10ms (co-located)
    medium — 10-100ms (nearby region)
    high   — 100-500ms (cross-region)
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class LatencyProfile:
    """A latency profile definition."""
    name: str = "zero"
    min_ms: float = 0.0
    max_ms: float = 0.0
    jitter_ms: float = 0.0
    description: str = ""


@dataclass
class LatencyResult:
    """Latency simulation result."""
    latency_ms: float = 0.0
    profile: str = "zero"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LatencySimulator:
    """Simulates order execution latency.

    Pre-built profiles for different trading environments.
    """

    PROFILES: Dict[str, LatencyProfile] = {
        "zero": LatencyProfile(name="zero", min_ms=0, max_ms=0, jitter_ms=0,
                               description="Zero latency (ideal)"),
        "low": LatencyProfile(name="low", min_ms=1, max_ms=10, jitter_ms=2,
                              description="Low latency (co-located)"),
        "medium": LatencyProfile(name="medium", min_ms=10, max_ms=100, jitter_ms=15,
                                 description="Medium latency (nearby region)"),
        "high": LatencyProfile(name="high", min_ms=100, max_ms=500, jitter_ms=50,
                               description="High latency (cross-region)"),
    }

    def __init__(self, profile: str = "zero"):
        self._profile_name = profile
        self._profile = self.PROFILES.get(profile, self.PROFILES["zero"])
        self._custom_profiles: Dict[str, LatencyProfile] = {}
        self.is_initialized = False

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("LatencySimulator initialized (profile=%s)", self._profile_name)

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    async def simulate(self) -> LatencyResult:
        """Simulate a single latency event."""
        profile = self._profile
        if profile.max_ms <= 0:
            return LatencyResult(latency_ms=0.0, profile=profile.name)

        base = random.uniform(profile.min_ms, profile.max_ms)
        jitter = random.uniform(-profile.jitter_ms, profile.jitter_ms)
        latency = max(0.0, base + jitter)

        return LatencyResult(latency_ms=latency, profile=profile.name)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_profile(self, name: str) -> None:
        if name in self.PROFILES:
            self._profile_name = name
            self._profile = self.PROFILES[name]
        elif name in self._custom_profiles:
            self._profile_name = name
            self._profile = self._custom_profiles[name]
        else:
            logger.warning("Unknown latency profile: %s", name)

    def register_profile(self, profile: LatencyProfile) -> None:
        self._custom_profiles[profile.name] = profile

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "profile": self._profile_name,
            "min_ms": self._profile.min_ms,
            "max_ms": self._profile.max_ms,
            "jitter_ms": self._profile.jitter_ms,
        }
