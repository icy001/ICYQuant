"""Satellite Intelligence Engine — analyzes satellite imagery and derived observations for economic signals."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .record import (
    AlternativeFeature,
    AlternativeRecord,
    SatelliteObservation,
    SignalStrength,
)


# ---------------------------------------------------------------------------
# Observation type configuration
# ---------------------------------------------------------------------------

_OBSERVATION_CONFIG: dict[str, dict] = {
    "factory_activity": {
        "description": "Manufacturing activity level from satellite imagery",
        "indicators": ["truck_count", "parking_density", "thermal_signature", "smoke_stack"],
        "thresholds": {"low": 30, "moderate": 50, "high": 70},
        "z_scale": 2.0,
    },
    "port_traffic": {
        "description": "Port / shipping traffic volume",
        "indicators": ["container_count", "ship_count", "crane_activity"],
        "thresholds": {"low": 25, "moderate": 50, "high": 75},
        "z_scale": 2.2,
    },
    "energy_consumption": {
        "description": "Energy consumption inferred from thermal / night-light data",
        "indicators": ["night_light_intensity", "thermal_output", "flare_activity"],
        "thresholds": {"low": 20, "moderate": 50, "high": 80},
        "z_scale": 1.8,
    },
    "parking_lot": {
        "description": "Retail / commercial parking lot occupancy",
        "indicators": ["car_count", "occupancy_rate", "turnover_rate"],
        "thresholds": {"low": 30, "moderate": 55, "high": 75},
        "z_scale": 1.5,
    },
    "construction": {
        "description": "Construction activity from land change detection",
        "indicators": ["land_change_area", "equipment_count", "progress_rate"],
        "thresholds": {"low": 15, "moderate": 40, "high": 65},
        "z_scale": 2.5,
    },
    "agriculture": {
        "description": "Agricultural activity from crop health / NDVI",
        "indicators": ["ndvi_index", "crop_area", "irrigation_pattern"],
        "thresholds": {"low": 20, "moderate": 50, "high": 80},
        "z_scale": 1.5,
    },
}


# ---------------------------------------------------------------------------
# Sector-to-observation mapping
# ---------------------------------------------------------------------------

_SECTOR_OBSERVATIONS: dict[str, list[str]] = {
    "semiconductor": ["factory_activity", "construction"],
    "retail": ["parking_lot", "port_traffic"],
    "energy": ["energy_consumption", "port_traffic"],
    "shipping": ["port_traffic"],
    "real_estate": ["construction"],
    "agriculture": ["agriculture"],
    "manufacturing": ["factory_activity", "port_traffic"],
    "automotive": ["factory_activity", "parking_lot"],
}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SatelliteResult:
    """Result of satellite intelligence analysis."""

    location: str = ""
    observation_type: str = ""
    activity_score: float = 0.0  # [0, 100]
    change_pct: float = 0.0
    activity_level: str = "moderate"  # low, moderate, high
    confidence: float = 0.5
    key_indicators: list[str] = field(default_factory=list)
    sector_signals: dict[str, str] = field(default_factory=dict)  # sector → signal
    summary: str = ""
    features: list[AlternativeFeature] = field(default_factory=list)

    @property
    def is_high_activity(self) -> bool:
        return self.activity_level == "high"

    @property
    def is_accelerating(self) -> bool:
        return self.change_pct > 5.0 and self.activity_score > 40

    @property
    def is_decelerating(self) -> bool:
        return self.change_pct < -5.0


@dataclass
class LocationProfile:
    """Aggregated satellite observations for a specific location."""

    location: str
    observations: dict[str, list[SatelliteResult]] = field(default_factory=dict)
    composite_activity: float = 0.0
    trend: str = "stable"  # improving, stable, declining
    affected_sectors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class SatelliteIntelligenceEngine:
    """Analyzes satellite-derived observations for economic and business activity signals.

    Capabilities:
    - Factory activity monitoring (truck count, parking density, thermal)
    - Port traffic analysis (container count, ship count, crane activity)
    - Energy consumption inference (night-light, thermal output)
    - Retail activity via parking lot occupancy
    - Construction activity from land change detection
    - Agriculture monitoring from NDVI / crop health
    - Sector-specific signal generation
    """

    def __init__(self) -> None:
        self._results: list[SatelliteResult] = []
        self._observations: list[SatelliteObservation] = []
        self._location_data: dict[str, list[SatelliteResult]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self, image: SatelliteObservation | AlternativeRecord | dict
    ) -> SatelliteResult:
        """Analyze a satellite observation and return structured intelligence."""
        if isinstance(image, SatelliteObservation):
            obs_type = image.observation_type
            location = image.location
            activity = image.activity_score
            change = image.change_pct
            tags = image.asset_tags
            self._observations.append(image)
        elif isinstance(image, AlternativeRecord):
            obs_type = image.metadata.get("observation_type", "unknown")
            location = image.metadata.get("location", "unknown")
            activity = float(image.metadata.get("activity_score", 0))
            change = float(image.metadata.get("change_pct", 0))
            tags = image.asset_tags
        elif isinstance(image, dict):
            obs_type = image.get("observation_type", "unknown")
            location = image.get("location", "unknown")
            activity = float(image.get("activity_score", 0))
            change = float(image.get("change_pct", 0))
            tags = image.get("asset_tags", [])
        else:
            obs_type = "unknown"
            location = "unknown"
            activity = 0.0
            change = 0.0
            tags = []

        config = _OBSERVATION_CONFIG.get(obs_type, {})
        thresholds = config.get("thresholds", {"low": 30, "moderate": 50, "high": 70})

        # Activity level classification
        if activity >= thresholds["high"]:
            activity_level = "high"
        elif activity >= thresholds["moderate"]:
            activity_level = "moderate"
        else:
            activity_level = "low"

        # Sector signal mapping
        sector_signals = self._map_to_sectors(obs_type, activity_level, change)

        # Confidence
        confidence = self._estimate_confidence(obs_type, activity, change)

        # Features
        features = self._generate_features(
            obs_type, location, activity, change, tags, activity_level
        )

        result = SatelliteResult(
            location=location,
            observation_type=obs_type,
            activity_score=activity,
            change_pct=change,
            activity_level=activity_level,
            confidence=confidence,
            key_indicators=config.get("indicators", []),
            sector_signals=sector_signals,
            summary=(
                f"{obs_type} @ {location}: activity={activity:.0f}/100 "
                f"(Δ{change:+.1f}%) → {activity_level}"
            ),
            features=features,
        )
        self._results.append(result)
        self._location_data[location].append(result)

        return result

    def analyze_batch(
        self, observations: list[SatelliteObservation | AlternativeRecord | dict]
    ) -> list[SatelliteResult]:
        """Analyze a batch of satellite observations."""
        return [self.analyze(o) for o in observations]

    def get_location_profile(self, location: str) -> LocationProfile:
        """Get aggregated satellite intelligence for a location."""
        results = self._location_data.get(location, [])
        if not results:
            return LocationProfile(location=location)

        # Group by observation type
        by_type: dict[str, list[SatelliteResult]] = defaultdict(list)
        for r in results:
            by_type[r.observation_type].append(r)

        # Composite activity
        all_scores = [r.activity_score for r in results]
        composite = sum(all_scores) / len(all_scores) if all_scores else 0.0

        # Trend from change_pct
        avg_change = sum(r.change_pct for r in results) / len(results)
        if avg_change > 3:
            trend = "improving"
        elif avg_change < -3:
            trend = "declining"
        else:
            trend = "stable"

        # Affected sectors
        sectors: set[str] = set()
        for r in results:
            sectors.update(r.sector_signals.keys())

        return LocationProfile(
            location=location,
            observations=dict(by_type),
            composite_activity=round(composite, 1),
            trend=trend,
            affected_sectors=sorted(sectors),
        )

    def get_sector_signals(self, sector: str) -> list[SatelliteResult]:
        """Get all satellite results relevant to a specific sector."""
        obs_types = _SECTOR_OBSERVATIONS.get(sector, [])
        return [r for r in self._results if r.observation_type in obs_types]

    def get_high_activity_locations(self) -> list[tuple[str, float]]:
        """Get locations sorted by composite activity (descending)."""
        scored: list[tuple[str, float]] = []
        for loc in self._location_data:
            profile = self.get_location_profile(loc)
            scored.append((loc, profile.composite_activity))
        return sorted(scored, key=lambda x: x[1], reverse=True)

    @property
    def history(self) -> list[SatelliteResult]:
        return list(self._results)

    @property
    def observation_count(self) -> int:
        return len(self._observations)

    def clear(self) -> None:
        self._results.clear()
        self._observations.clear()
        self._location_data.clear()

    # ------------------------------------------------------------------
    # Internal: Sector Mapping
    # ------------------------------------------------------------------

    def _map_to_sectors(
        self, obs_type: str, activity_level: str, change_pct: float
    ) -> dict[str, str]:
        """Map satellite observation to sector-level signals."""
        signals: dict[str, str] = {}

        for sector, obs_list in _SECTOR_OBSERVATIONS.items():
            if obs_type in obs_list:
                if activity_level == "high" and change_pct > 0:
                    signals[sector] = "BULLISH"
                elif activity_level == "high" and change_pct <= 0:
                    signals[sector] = "STABLE_POSITIVE"
                elif activity_level == "low" and change_pct < 0:
                    signals[sector] = "BEARISH"
                elif activity_level == "low" and change_pct >= 0:
                    signals[sector] = "STABLE_NEGATIVE"
                else:
                    signals[sector] = "NEUTRAL"

        return signals

    def _estimate_confidence(
        self, obs_type: str, activity_score: float, change_pct: float
    ) -> float:
        """Estimate confidence in the satellite intelligence signal."""
        base = 0.5 if obs_type in _OBSERVATION_CONFIG else 0.3

        # Extreme activity levels are more reliable
        extreme_factor = min(0.2, abs(activity_score - 50) / 200.0)

        # Larger changes are more reliable
        change_factor = min(0.15, abs(change_pct) / 100.0)

        return min(0.9, base + extreme_factor + change_factor)

    # ------------------------------------------------------------------
    # Internal: Feature Generation
    # ------------------------------------------------------------------

    def _generate_features(
        self,
        obs_type: str,
        location: str,
        activity: float,
        change: float,
        tags: list[str],
        activity_level: str,
    ) -> list[AlternativeFeature]:
        """Generate alpha features from satellite observations."""
        features: list[AlternativeFeature] = []
        config = _OBSERVATION_CONFIG.get(obs_type, {})
        z_scale = config.get("z_scale", 2.0)

        # Normalize activity to z-score-like scale
        z_score = (activity - 50) / 25.0 * z_scale

        signal = (
            SignalStrength.STRONG
            if activity_level == "high" and abs(change) > 5
            else SignalStrength.MODERATE
            if activity_level != "low"
            else SignalStrength.WEAK
        )

        for tag in tags:
            features.append(
                AlternativeFeature(
                    name=f"satellite_{obs_type}_{tag}",
                    value=activity,
                    category="satellite",
                    asset_tag=tag,
                    z_score=z_score,
                    signal_strength=signal,
                    metadata={"location": location, "change_pct": change},
                )
            )

        return features
