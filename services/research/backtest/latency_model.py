"""Latency Model — trade execution latency simulation.

Models end-to-end latency from order submission to fill acknowledgment,
enabling HFT vs L/S strategy differentiation in backtesting.

Components::

    Network → OMS → Exchange → Matching → Total Latency
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LatencyComponent(str, Enum):
    """Latency components in the trading lifecycle."""

    NETWORK = "network"
    OMS = "oms"
    EXCHANGE = "exchange"
    MATCHING = "matching"
    TOTAL = "total"


@dataclass
class LatencyProfile:
    """Latency breakdown for a trading path."""

    network_ms: float = 1.0
    oms_ms: float = 0.5
    exchange_ms: float = 0.5
    matching_ms: float = 0.2
    jitter_ms: float = 0.5  # max random jitter

    @property
    def total_ms(self) -> float:
        return self.network_ms + self.oms_ms + self.exchange_ms + self.matching_ms

    def sample(self) -> float:
        """Sample a single latency value with jitter."""
        base = self.total_ms
        jitter = random.uniform(0, self.jitter_ms)
        return base + jitter


class LatencyModel:
    """Trade execution latency model.

    Supports configurable latency profiles for different trading
    scenarios:
    * HFT (sub-millisecond): total ~0.5ms
    * Low Latency: total ~5ms
    * Standard: total ~50ms
    * Retail: total ~500ms

    Usage::

        model = LatencyModel(profile="standard")
        latency = model.get_latency()  # random sample from distribution
    """

    # Pre-configured latency profiles
    PROFILES: Dict[str, LatencyProfile] = {
        "hft": LatencyProfile(
            network_ms=0.1, oms_ms=0.05, exchange_ms=0.3, matching_ms=0.05, jitter_ms=0.1,
        ),
        "low_latency": LatencyProfile(
            network_ms=1.0, oms_ms=1.0, exchange_ms=2.0, matching_ms=1.0, jitter_ms=2.0,
        ),
        "standard": LatencyProfile(
            network_ms=10.0, oms_ms=10.0, exchange_ms=20.0, matching_ms=10.0, jitter_ms=10.0,
        ),
        "retail": LatencyProfile(
            network_ms=100.0, oms_ms=100.0, exchange_ms=200.0, matching_ms=100.0, jitter_ms=100.0,
        ),
    }

    def __init__(
        self,
        profile: str = "standard",
        custom_profile: Optional[LatencyProfile] = None,
    ) -> None:
        self._profile_name = profile
        self._profile = custom_profile or self.PROFILES.get(
            profile, self.PROFILES["standard"]
        )
        self._total_samples = 0
        self._total_latency_ms = 0.0
        self._min_latency_ms = float("inf")
        self._max_latency_ms = 0.0

    # ── latency sampling ───────────────────────────────────────────────────

    def get_latency(self) -> float:
        """Sample a single latency value (ms) from the current profile."""
        latency = self._profile.sample()
        self._total_samples += 1
        self._total_latency_ms += latency
        self._min_latency_ms = min(self._min_latency_ms, latency)
        self._max_latency_ms = max(self._max_latency_ms, latency)
        return latency

    def get_latency_breakdown(self) -> Dict[str, float]:
        """Get the expected latency for each component."""
        return {
            LatencyComponent.NETWORK.value: self._profile.network_ms,
            LatencyComponent.OMS.value: self._profile.oms_ms,
            LatencyComponent.EXCHANGE.value: self._profile.exchange_ms,
            LatencyComponent.MATCHING.value: self._profile.matching_ms,
            LatencyComponent.TOTAL.value: self._profile.total_ms,
        }

    def sample_and_apply(
        self, market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Sample a latency value and return it with metadata.

        In a real system this would also shift timestamps in market data
        to simulate delayed price reception.

        Args:
            market_data: Current market data snapshot.

        Returns:
            The market data dict with added latency field.
        """
        latency = self.get_latency()
        market_data["_latency_ms"] = latency
        market_data["_latency_profile"] = self._profile_name
        return market_data

    # ── profile management ─────────────────────────────────────────────────

    def set_profile(
        self,
        profile: str,
        custom: Optional[LatencyProfile] = None,
    ) -> None:
        """Switch to a different latency profile."""
        self._profile_name = profile
        self._profile = custom or self.PROFILES.get(profile, self.PROFILES["standard"])
        logger.info("Latency profile set to: %s (%.2fms avg)", profile, self._profile.total_ms)

    def set_custom_profile(self, profile: LatencyProfile) -> None:
        """Set a completely custom latency profile."""
        self._profile_name = "custom"
        self._profile = profile

    def get_profile_name(self) -> str:
        return self._profile_name

    # ── query ──────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return latency model statistics."""
        return {
            "profile": self._profile_name,
            "expected_total_ms": self._profile.total_ms,
            "breakdown": self.get_latency_breakdown(),
            "samples": self._total_samples,
            "avg_latency_ms": (
                self._total_latency_ms / self._total_samples
                if self._total_samples > 0 else 0
            ),
            "min_latency_ms": self._min_latency_ms if self._total_samples > 0 else 0,
            "max_latency_ms": self._max_latency_ms,
        }
