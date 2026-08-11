"""
Exposure Manager
================
Real-time exposure monitoring and control across multiple dimensions.

Dimensions:
    Gross Exposure, Net Exposure, Sector Exposure,
    Factor Exposure, Currency Exposure
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExposureType(str, Enum):
    """Types of exposure to monitor."""

    GROSS = "gross"
    NET = "net"
    SECTOR = "sector"
    FACTOR = "factor"
    CURRENCY = "currency"
    INSTRUMENT = "instrument"
    STRATEGY = "strategy"


@dataclass
class ExposureLimit:
    """An exposure limit for a specific dimension."""

    exposure_type: ExposureType
    key: str = ""  # e.g., sector name, factor name, currency
    max_long: float = float("inf")
    max_short: float = float("inf")
    max_gross: float = float("inf")
    max_net: float = float("inf")
    enabled: bool = True

    def check(self, long_val: float, short_val: float = 0.0) -> List[str]:
        """Check values against limits. Returns list of violations."""
        violations = []
        gross = long_val + abs(short_val)
        net = long_val - abs(short_val)

        if self.max_long != float("inf") and long_val > self.max_long:
            violations.append(f"{self.key}: long {long_val:.2f} > {self.max_long:.2f}")
        if self.max_short != float("inf") and abs(short_val) > self.max_short:
            violations.append(f"{self.key}: short {abs(short_val):.2f} > {self.max_short:.2f}")
        if self.max_gross != float("inf") and gross > self.max_gross:
            violations.append(f"{self.key}: gross {gross:.2f} > {self.max_gross:.2f}")
        if self.max_net != float("inf") and abs(net) > self.max_net:
            violations.append(f"{self.key}: net {abs(net):.2f} > {self.max_net:.2f}")

        return violations


@dataclass
class ExposureReport:
    """Comprehensive exposure report."""

    portfolio_id: str = ""
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    leverage: float = 0.0

    sector_exposures: Dict[str, float] = field(default_factory=dict)
    factor_exposures: Dict[str, float] = field(default_factory=dict)
    currency_exposures: Dict[str, float] = field(default_factory=dict)
    strategy_exposures: Dict[str, float] = field(default_factory=dict)

    limit_hits: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "gross_exposure": self.gross_exposure,
            "net_exposure": self.net_exposure,
            "long_exposure": self.long_exposure,
            "short_exposure": self.short_exposure,
            "leverage": self.leverage,
            "sector_exposures": self.sector_exposures,
            "factor_exposures": self.factor_exposures,
            "currency_exposures": self.currency_exposures,
            "strategy_exposures": self.strategy_exposures,
            "limit_hits": self.limit_hits,
            "warnings": self.warnings,
            "timestamp": self.timestamp.isoformat(),
        }


class ExposureManager:
    """
    Real-time Exposure Manager.

    Monitors and controls exposure across:
    - Gross/Net exposure
    - Sector concentration
    - Factor exposure
    - Currency exposure
    - Per-instrument limits
    - Per-strategy limits
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False

        # Exposure limits
        self._limits: Dict[str, ExposureLimit] = {}

        # Current exposure state (from portfolio)
        self._current_state: Dict[str, Any] = {}

        # Metrics
        self._limit_hit_count: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return

        # Load limits from config
        limits_config = self._config.get("limits", {})

        # Global limits
        if "gross" in limits_config:
            g = limits_config["gross"]
            self._limits["gross"] = ExposureLimit(
                exposure_type=ExposureType.GROSS,
                key="portfolio",
                max_gross=g.get("max", float("inf")),
                max_net=g.get("max_net", float("inf")),
            )

        if "net" in limits_config:
            n = limits_config["net"]
            self._limits["net"] = ExposureLimit(
                exposure_type=ExposureType.NET,
                key="portfolio",
                max_long=n.get("max_long", float("inf")),
                max_short=n.get("max_short", float("inf")),
                max_net=n.get("max_net", float("inf")),
            )

        # Sector limits
        sectors = limits_config.get("sectors", {})
        for sector_name, sector_limits in sectors.items():
            self._limits[f"sector_{sector_name}"] = ExposureLimit(
                exposure_type=ExposureType.SECTOR,
                key=sector_name,
                max_long=sector_limits.get("max_long", float("inf")),
                max_short=sector_limits.get("max_short", float("inf")),
                max_gross=sector_limits.get("max_gross", float("inf")),
                max_net=sector_limits.get("max_net", float("inf")),
            )

        # Factor limits
        factors = limits_config.get("factors", {})
        for factor_name, factor_limits in factors.items():
            self._limits[f"factor_{factor_name}"] = ExposureLimit(
                exposure_type=ExposureType.FACTOR,
                key=factor_name,
                max_long=factor_limits.get("max_long", float("inf")),
                max_short=factor_limits.get("max_short", float("inf")),
                max_net=factor_limits.get("max_net", float("inf")),
            )

        # Currency limits
        currencies = limits_config.get("currencies", {})
        for ccy, ccy_limits in currencies.items():
            self._limits[f"currency_{ccy}"] = ExposureLimit(
                exposure_type=ExposureType.CURRENCY,
                key=ccy,
                max_gross=ccy_limits.get("max_gross", float("inf")),
                max_net=ccy_limits.get("max_net", float("inf")),
            )

        self._initialized = True
        logger.info("ExposureManager initialized with %d limits", len(self._limits))

    async def shutdown(self) -> None:
        self._limits.clear()
        self._current_state.clear()
        self._initialized = False
        logger.info("ExposureManager shut down")

    # ------------------------------------------------------------------
    # Limit Management
    # ------------------------------------------------------------------

    def set_limit(self, key: str, limit: ExposureLimit) -> None:
        """Set or update an exposure limit."""
        self._limits[key] = limit
        logger.debug("Exposure limit set: %s (%s)", key, limit.exposure_type.value)

    def remove_limit(self, key: str) -> bool:
        if key in self._limits:
            del self._limits[key]
            return True
        return False

    def get_limit(self, key: str) -> Optional[ExposureLimit]:
        return self._limits.get(key)

    def list_limits(self) -> List[ExposureLimit]:
        return list(self._limits.values())

    # ------------------------------------------------------------------
    # Exposure Check
    # ------------------------------------------------------------------

    def _aggregate_positions(
        self,
        positions: List[Dict[str, Any]],
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Aggregate positions into exposure metrics."""
        gross = 0.0
        net = 0.0
        long_val = 0.0
        short_val = 0.0
        sectors: Dict[str, float] = {}
        currencies: Dict[str, float] = {}
        strategies: Dict[str, float] = {}

        total_equity = (portfolio_state or {}).get("equity", 1.0)

        for pos in positions:
            value = pos.get("position_value", pos.get("allocated_capital", 0.0))
            direction = pos.get("direction", "").upper()

            gross += abs(value)
            net += value if "SHORT" not in direction else -value

            if "SHORT" in direction:
                short_val += abs(value)
            else:
                long_val += value

            # Sector aggregation
            sector = pos.get("sector", pos.get("metadata", {}).get("sector", "unknown"))
            sectors[sector] = sectors.get(sector, 0.0) + value

            # Currency aggregation
            ccy = pos.get("currency", pos.get("metadata", {}).get("currency", "USD"))
            currencies[ccy] = currencies.get(ccy, 0.0) + value

            # Strategy aggregation
            sid = pos.get("strategy_id", "unknown")
            strategies[sid] = strategies.get(sid, 0.0) + value

        leverage = gross / total_equity if total_equity > 0 else 0.0

        return {
            "gross": gross,
            "net": net,
            "long_val": long_val,
            "short_val": short_val,
            "sectors": sectors,
            "currencies": currencies,
            "strategies": strategies,
            "leverage": leverage,
            "equity": total_equity,
        }

    async def check(
        self,
        positions: List[Dict[str, Any]],
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> ExposureReport:
        """
        Check exposure limits against current positions.

        Args:
            positions: List of position dicts.
            portfolio_state: Current portfolio state.

        Returns:
            ExposureReport with all exposure metrics and limit violations.
        """
        if not self._initialized:
            await self.initialize()

        agg = self._aggregate_positions(positions, portfolio_state)

        report = ExposureReport(
            portfolio_id=(portfolio_state or {}).get("portfolio_id", ""),
            gross_exposure=agg["gross"],
            net_exposure=agg["net"],
            long_exposure=agg["long_val"],
            short_exposure=agg["short_val"],
            leverage=agg["leverage"],
            sector_exposures=agg["sectors"],
            currency_exposures=agg["currencies"],
            strategy_exposures=agg["strategies"],
        )

        # Check all limits
        limit_hits = []
        warnings = []

        for key, limit in self._limits.items():
            if not limit.enabled:
                continue

            if limit.exposure_type == ExposureType.GROSS:
                violations = limit.check(agg["gross"], 0)
            elif limit.exposure_type == ExposureType.NET:
                violations = limit.check(agg["net"], 0)
            elif limit.exposure_type == ExposureType.SECTOR:
                sector_val = agg["sectors"].get(limit.key, 0.0)
                violations = limit.check(sector_val)
            elif limit.exposure_type == ExposureType.CURRENCY:
                ccy_val = agg["currencies"].get(limit.key, 0.0)
                violations = limit.check(ccy_val)
            elif limit.exposure_type == ExposureType.STRATEGY:
                strat_val = agg["strategies"].get(limit.key, 0.0)
                violations = limit.check(strat_val)
            else:
                continue

            for v in violations:
                limit_hits.append(f"[{limit.exposure_type.value}] {v}")
                self._limit_hit_count[key] = self._limit_hit_count.get(key, 0) + 1

        # Add warnings for near-limit situations (within 80%)
        for key, limit in self._limits.items():
            if not limit.enabled:
                continue
            if limit.max_gross != float("inf") and agg["gross"] > limit.max_gross * 0.8:
                warnings.append(f"Gross exposure at {agg['gross']/limit.max_gross:.0%} of limit")
            if limit.max_net != float("inf") and abs(agg["net"]) > limit.max_net * 0.8:
                warnings.append(f"Net exposure at {abs(agg['net'])/limit.max_net:.0%} of limit")

        report.limit_hits = limit_hits
        report.warnings = warnings

        if limit_hits:
            logger.warning("Exposure check: %d limit(s) hit", len(limit_hits))
        if warnings:
            logger.info("Exposure check: %d warning(s)", len(warnings))

        return report

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "limit_hit_counts": dict(self._limit_hit_count),
            "total_limits": len(self._limits),
        }

    @property
    def is_initialized(self) -> bool:
        return self._initialized
