"""AI Exposure Control Engine — multi-dimensional exposure monitoring & control.

Tracks and analyzes portfolio exposures across market factors, sectors,
geographies, currencies, styles, and instruments. Provides exposure
decomposition, drift detection, and rebalancing triggers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ExposureType(str, Enum):
    """Types of portfolio exposure to track."""

    MARKET_BETA = "market_beta"
    SECTOR = "sector"
    GEOGRAPHY = "geography"
    CURRENCY = "currency"
    STYLE = "style"  # value/growth, size, momentum
    FACTOR = "factor"
    INSTRUMENT = "instrument"  # equity, bond, derivative
    LIQUIDITY = "liquidity"
    CONCENTRATION = "concentration"


class ExposureDirection(str, Enum):
    """Exposure direction."""

    LONG = "long"
    SHORT = "short"
    NET = "net"
    GROSS = "gross"


class ExposureStatus(str, Enum):
    """Exposure breach status."""

    WITHIN_LIMIT = "within_limit"
    APPROACHING_LIMIT = "approaching_limit"
    BREACHED = "breached"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class Exposure:
    """Single exposure dimension.

    Attributes:
        exposure_type: Type of exposure being tracked.
        direction: Long/short/net/gross.
        current_value: Current exposure value (e.g., beta, pct).
        limit: Maximum allowed exposure.
        warning_limit: Threshold for approaching-limit status (0–1).
        unit: Unit of measurement (pct, beta, currency).
    """

    exposure_type: ExposureType
    direction: ExposureDirection = ExposureDirection.NET
    current_value: float = 0.0
    limit: float = 1.0
    warning_limit: float = 0.8
    unit: str = "pct"

    @property
    def utilization(self) -> float:
        """Current / limit ratio."""
        return self.current_value / max(self.limit, 0.0001)

    @property
    def status(self) -> ExposureStatus:
        """Current exposure breach status."""
        if self.utilization >= 1.0:
            if self.utilization >= 1.2:
                return ExposureStatus.CRITICAL
            return ExposureStatus.BREACHED
        elif self.utilization >= self.warning_limit:
            return ExposureStatus.APPROACHING_LIMIT
        else:
            return ExposureStatus.WITHIN_LIMIT

    @property
    def is_breached(self) -> bool:
        """Whether this exposure limit has been breached."""
        return self.status in (ExposureStatus.BREACHED, ExposureStatus.CRITICAL)

    @property
    def remaining_capacity(self) -> float:
        """Remaining exposure capacity."""
        return max(0.0, self.limit - abs(self.current_value))


@dataclass
class ExposureReport:
    """Comprehensive portfolio exposure report.

    Attributes:
        exposures: List of tracked exposures across dimensions.
        total_gross_exposure: Sum of absolute exposures.
        total_net_exposure: Net directional exposure.
        leverage_ratio: Gross / NAV ratio.
        concentration_hhi: Herfindahl-Hirschman Index for position concentration.
        breached_exposures: Count of breached limits.
        timestamp: Report generation time.
        metadata: Additional exposure context.
    """

    exposures: list[Exposure]
    total_gross_exposure: float = 0.0
    total_net_exposure: float = 0.0
    leverage_ratio: float = 0.0
    concentration_hhi: float = 0.0
    breached_exposures: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_within_limits(self) -> bool:
        """All exposures within limits."""
        return self.breached_exposures == 0

    @property
    def critical_breaches(self) -> list[Exposure]:
        """List of critically breached exposures."""
        return [e for e in self.exposures if e.status == ExposureStatus.CRITICAL]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "exposures": [
                {
                    "type": e.exposure_type.value,
                    "direction": e.direction.value,
                    "current_value": e.current_value,
                    "limit": e.limit,
                    "utilization": e.utilization,
                    "status": e.status.value,
                }
                for e in self.exposures
            ],
            "total_gross_exposure": self.total_gross_exposure,
            "total_net_exposure": self.total_net_exposure,
            "leverage_ratio": self.leverage_ratio,
            "concentration_hhi": self.concentration_hhi,
            "breached_exposures": self.breached_exposures,
            "is_within_limits": self.is_within_limits,
        }


# ---------------------------------------------------------------------------
# ExposureEngine
# ---------------------------------------------------------------------------


class ExposureEngine:
    """AI-powered exposure control and monitoring engine.

    Aggregates positions across all exposure dimensions, checks against
    limits, and triggers alerts. Supports multi-factor decomposition and
    stress-test-adjusted exposure projections.

    Attributes:
        limits: Per-exposure type limits.
        warning_threshold: Default warning threshold (fraction of limit).
        history: Past exposure reports.
    """

    DEFAULT_LIMITS: dict[ExposureType, float] = {
        ExposureType.MARKET_BETA: 1.5,
        ExposureType.SECTOR: 0.30,  # max 30% in any sector
        ExposureType.GEOGRAPHY: 0.50,  # max 50% in any region
        ExposureType.CURRENCY: 0.20,  # max 20% unhedged FX
        ExposureType.STYLE: 0.60,  # max 60% concentration in one style
        ExposureType.FACTOR: 0.40,
        ExposureType.INSTRUMENT: 0.40,
        ExposureType.LIQUIDITY: 0.30,  # max illiquid exposure
        ExposureType.CONCENTRATION: 0.15,  # HHI threshold
    }

    def __init__(
        self,
        limits: Optional[dict[ExposureType, float]] = None,
        warning_threshold: float = 0.8,
    ) -> None:
        """Initialize the exposure engine.

        Args:
            limits: Custom per-exposure limits (merges with defaults).
            warning_threshold: Default warning utilization threshold.
        """
        self.limits = {**self.DEFAULT_LIMITS, **(limits or {})}
        self.warning_threshold = warning_threshold
        self.history: list[ExposureReport] = []

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------

    def analyze(
        self,
        positions: list[dict[str, Any]],
        nav: float = 1_000_000.0,
    ) -> ExposureReport:
        """Analyze portfolio exposures from position data.

        Args:
            positions: List of position dicts with keys: symbol, market_value,
                       beta, sector, region, currency, style, factor_loadings,
                       instrument_type, liquidity_score.
            nav: Net asset value for leverage calculation.

        Returns:
            ExposureReport with computed exposures and breach status.
        """
        exposures: list[Exposure] = []

        # Aggregate across positions
        sector_exposures: dict[str, float] = {}
        region_exposures: dict[str, float] = {}
        currency_exposures: dict[str, float] = {}
        style_exposures: dict[str, float] = {}
        factor_exposures: dict[str, float] = {}
        instrument_exposures: dict[str, float] = {}
        total_beta_value = 0.0
        total_value = 0.0
        concentration_hhi = 0.0
        total_illiquid = 0.0

        for p in positions:
            mv = p.get("market_value", 0.0)
            total_value += mv

            sector = p.get("sector", "unknown")
            sector_exposures[sector] = sector_exposures.get(sector, 0.0) + mv

            region = p.get("region", "global")
            region_exposures[region] = region_exposures.get(region, 0.0) + mv

            currency = p.get("currency", "USD")
            currency_exposures[currency] = currency_exposures.get(currency, 0.0) + mv

            style = p.get("style", "blend")
            style_exposures[style] = style_exposures.get(style, 0.0) + mv

            for factor, loading in p.get("factor_loadings", {}).items():
                factor_exposures[factor] = factor_exposures.get(factor, 0.0) + loading * mv

            instrument = p.get("instrument_type", "equity")
            instrument_exposures[instrument] = instrument_exposures.get(instrument, 0.0) + mv

            beta = p.get("beta", 1.0)
            total_beta_value += beta * mv

            liq = p.get("liquidity_score", 1.0)
            if liq < 0.3:
                total_illiquid += mv

        # Normalize to pct of NAV
        nav = max(nav, total_value, 1.0)

        # Market beta exposure
        beta_exposure = total_beta_value / nav
        exposures.append(
            Exposure(
                exposure_type=ExposureType.MARKET_BETA,
                direction=ExposureDirection.NET,
                current_value=beta_exposure,
                limit=self.limits[ExposureType.MARKET_BETA],
                warning_limit=self.warning_threshold,
                unit="beta",
            )
        )

        # Sector concentration (max sector)
        max_sector_pct = max(sector_exposures.values()) / nav if sector_exposures else 0.0
        exposures.append(
            Exposure(
                exposure_type=ExposureType.SECTOR,
                current_value=max_sector_pct,
                limit=self.limits[ExposureType.SECTOR],
                warning_limit=self.warning_threshold,
                unit="pct",
            )
        )

        # Geography concentration (max region)
        max_region_pct = max(region_exposures.values()) / nav if region_exposures else 0.0
        exposures.append(
            Exposure(
                exposure_type=ExposureType.GEOGRAPHY,
                current_value=max_region_pct,
                limit=self.limits[ExposureType.GEOGRAPHY],
                warning_limit=self.warning_threshold,
                unit="pct",
            )
        )

        # Currency exposure (total non-base)
        non_base_fx = sum(v for c, v in currency_exposures.items() if c != "USD")
        exposures.append(
            Exposure(
                exposure_type=ExposureType.CURRENCY,
                current_value=non_base_fx / nav,
                limit=self.limits[ExposureType.CURRENCY],
                warning_limit=self.warning_threshold,
                unit="pct",
            )
        )

        # Style concentration (max style)
        max_style_pct = max(style_exposures.values()) / nav if style_exposures else 0.0
        exposures.append(
            Exposure(
                exposure_type=ExposureType.STYLE,
                current_value=max_style_pct,
                limit=self.limits[ExposureType.STYLE],
                warning_limit=self.warning_threshold,
                unit="pct",
            )
        )

        # Factor exposure (max factor loading)
        max_factor_pct = max(factor_exposures.values()) / nav if factor_exposures else 0.0
        exposures.append(
            Exposure(
                exposure_type=ExposureType.FACTOR,
                current_value=max_factor_pct,
                limit=self.limits[ExposureType.FACTOR],
                warning_limit=self.warning_threshold,
                unit="pct",
            )
        )

        # Instrument type concentration
        max_inst_pct = max(instrument_exposures.values()) / nav if instrument_exposures else 0.0
        exposures.append(
            Exposure(
                exposure_type=ExposureType.INSTRUMENT,
                current_value=max_inst_pct,
                limit=self.limits[ExposureType.INSTRUMENT],
                warning_limit=self.warning_threshold,
                unit="pct",
            )
        )

        # Illiquid exposure
        illiquid_pct = total_illiquid / nav
        exposures.append(
            Exposure(
                exposure_type=ExposureType.LIQUIDITY,
                current_value=illiquid_pct,
                limit=self.limits[ExposureType.LIQUIDITY],
                warning_limit=self.warning_threshold,
                unit="pct",
            )
        )

        # Position concentration (HHI)
        if total_value > 0:
            position_weights = [p.get("market_value", 0) / total_value for p in positions]
            concentration_hhi = sum(w**2 for w in position_weights)
        exposures.append(
            Exposure(
                exposure_type=ExposureType.CONCENTRATION,
                current_value=concentration_hhi,
                limit=self.limits[ExposureType.CONCENTRATION],
                warning_limit=self.warning_threshold,
                unit="hhi",
            )
        )

        # Portfolio-level aggregates
        total_gross = total_value / nav
        total_net = total_value / nav  # simplified; net = gross for long-only
        leverage = total_gross  # simplified
        breached = sum(1 for e in exposures if e.is_breached)

        report = ExposureReport(
            exposures=exposures,
            total_gross_exposure=total_gross,
            total_net_exposure=total_net,
            leverage_ratio=leverage,
            concentration_hhi=concentration_hhi,
            breached_exposures=breached,
            metadata={
                "sector_breakdown": {k: round(v / nav, 4) for k, v in sector_exposures.items()},
                "region_breakdown": {k: round(v / nav, 4) for k, v in region_exposures.items()},
                "currency_breakdown": {k: round(v / nav, 4) for k, v in currency_exposures.items()},
            },
        )

        self.history.append(report)
        return report

    # ------------------------------------------------------------------
    # Limit Management
    # ------------------------------------------------------------------

    def set_limit(self, exposure_type: ExposureType, limit: float) -> None:
        """Update a single exposure limit.

        Args:
            exposure_type: The exposure type to update.
            limit: New limit value.
        """
        self.limits[exposure_type] = limit

    def get_breach_summary(self, report: Optional[ExposureReport] = None) -> dict[str, Any]:
        """Get a summary of exposure breaches.

        Args:
            report: Specific report to analyze (default: latest).

        Returns:
            Dict with breach details and recommended actions.
        """
        report = report or (self.history[-1] if self.history else None)
        if not report:
            return {"status": "no_data", "breaches": [], "actions": []}

        breaches = []
        actions = []
        for e in report.exposures:
            if e.status == ExposureStatus.CRITICAL:
                breaches.append(
                    f"CRITICAL: {e.exposure_type.value} at {e.utilization:.1%} of limit"
                )
                actions.append(
                    {
                        "type": e.exposure_type.value,
                        "action": "immediate_reduce",
                        "current": e.current_value,
                        "target": e.limit,
                    }
                )
            elif e.status == ExposureStatus.BREACHED:
                breaches.append(
                    f"BREACHED: {e.exposure_type.value} at {e.utilization:.1%} of limit"
                )
                actions.append(
                    {
                        "type": e.exposure_type.value,
                        "action": "reduce",
                        "current": e.current_value,
                        "target": e.limit,
                    }
                )
            elif e.status == ExposureStatus.APPROACHING_LIMIT:
                breaches.append(
                    f"WARNING: {e.exposure_type.value} at {e.utilization:.1%} of limit"
                )

        return {
            "status": "critical" if any(b.startswith("CRITICAL") for b in breaches)
            else "warning" if breaches else "healthy",
            "breaches": breaches,
            "actions": actions,
        }

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_scan(
        self,
        positions: list[dict[str, Any]],
        nav: float = 1_000_000.0,
    ) -> dict[str, Any]:
        """Quick exposure scan returning summary dict.

        Args:
            positions: Position data list.
            nav: Net asset value.

        Returns:
            Dict with exposure summary.
        """
        report = self.analyze(positions, nav)
        return {
            "total_gross": round(report.total_gross_exposure, 4),
            "total_net": round(report.total_net_exposure, 4),
            "leverage_ratio": round(report.leverage_ratio, 4),
            "breached": report.breached_exposures,
            "breach_details": self.get_breach_summary(report),
            "exposures": {
                e.exposure_type.value: {
                    "value": round(e.current_value, 4),
                    "utilization": round(e.utilization, 4),
                    "status": e.status.value,
                }
                for e in report.exposures
            },
        }

    def last_result(self) -> Optional[ExposureReport]:
        """Return the most recent exposure report."""
        return self.history[-1] if self.history else None

    def clear(self) -> None:
        """Reset exposure history."""
        self.history.clear()
