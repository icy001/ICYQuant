"""
Liquidity Shock — Sudden, discrete liquidity events with contagion propagation.

Models abrupt liquidity deterioration events:
- Single-asset shocks (earnings surprise, news)
- Contagion/correlation-driven spread
- Systemic multi-asset events
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from .liquidity_profile import LiquidityProfile
from .liquidity_regime import LiquidityRegimeDetector


class ShockType(str, Enum):
    SINGLE_ASSET = "single_asset"
    SECTOR_WIDE = "sector_wide"
    CORRELATION_DRIVEN = "correlation_driven"
    MARKET_WIDE = "market_wide"
    SYSTEMIC = "systemic"
    IDIOSYNCRATIC = "idiosyncratic"


class ShockPropagation(str, Enum):
    NONE = "none"          # Isolated to one asset
    DIRECT = "direct"      # Affects directly correlated assets
    INDIRECT = "indirect"   # Second-order effects
    CASCADING = "cascading" # Full market impact


@dataclass
class LiquidityShock:
    """A discrete liquidity shock event."""

    shock_id: str = field(default_factory=lambda: f"LSH-{uuid.uuid4().hex[:8]}")
    shock_type: ShockType = ShockType.SINGLE_ASSET
    propagation: ShockPropagation = ShockPropagation.NONE

    # Source asset
    source_asset: str = ""
    source_severity: float = 0.0  # 0-1 scale

    # Shock magnitudes
    volume_drop_pct: float = 0.0      # % volume decline
    spread_widening_x: float = 1.0    # spread multiplier
    depth_drop_pct: float = 0.0       # % depth decline
    volatility_spike_x: float = 1.0   # volatility multiplier

    # Contagion
    related_assets: List[str] = field(default_factory=list)
    correlation_matrix: Optional[Dict[str, Dict[str, float]]] = None
    contagion_decay: float = 0.5       # decay per hop (0-1)
    max_hops: int = 3

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shock_id": self.shock_id,
            "shock_type": self.shock_type.value,
            "propagation": self.propagation.value,
            "source_asset": self.source_asset,
            "source_severity": self.source_severity,
            "volume_drop_pct": self.volume_drop_pct,
            "spread_widening_x": self.spread_widening_x,
            "depth_drop_pct": self.depth_drop_pct,
            "volatility_spike_x": self.volatility_spike_x,
            "related_assets": self.related_assets,
            "contagion_decay": self.contagion_decay,
            "max_hops": self.max_hops,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ShockedProfile:
    """A liquidity profile after shock application."""

    asset: str = ""
    original_profile: Optional[LiquidityProfile] = None
    shock: Optional[LiquidityShock] = None
    propagation_hop: int = 0
    severity_received: float = 0.0

    # Shocked values
    shocked_volume: float = 0.0
    shocked_spread_bps: float = 0.0
    shocked_depth: float = 0.0
    shocked_volatility: float = 0.0
    shocked_liquidity_score: float = 0.0
    is_directly_affected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset,
            "propagation_hop": self.propagation_hop,
            "severity_received": self.severity_received,
            "shocked_volume": self.shocked_volume,
            "shocked_spread_bps": self.shocked_spread_bps,
            "shocked_depth": self.shocked_depth,
            "shocked_volatility": self.shocked_volatility,
            "shocked_liquidity_score": self.shocked_liquidity_score,
            "is_directly_affected": self.is_directly_affected,
        }


@dataclass
class ShockResult:
    """Complete result of a liquidity shock event."""

    shock: LiquidityShock = field(default_factory=LiquidityShock)
    affected_assets: List[ShockedProfile] = field(default_factory=list)
    total_assets_affected: int = 0
    systemic_severity: float = 0.0
    regime_shift_detected: bool = False
    new_regime: str = "UNKNOWN"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shock": self.shock.to_dict(),
            "total_assets_affected": self.total_assets_affected,
            "systemic_severity": self.systemic_severity,
            "regime_shift_detected": self.regime_shift_detected,
            "new_regime": self.new_regime,
            "affected_profiles": [a.to_dict() for a in self.affected_assets],
        }


class ShockPropagationEngine:
    """Propagates liquidity shocks through asset correlation networks."""

    def __init__(self):
        self._regime_detector = LiquidityRegimeDetector()
        self._correlations: Dict[str, Dict[str, float]] = {}

    def set_correlations(self, corr_matrix: Dict[str, Dict[str, float]]) -> None:
        """Set the asset correlation matrix for propagation."""
        self._correlations = corr_matrix

    def propagate(self,
                  shock: LiquidityShock,
                  profiles: Dict[str, LiquidityProfile]) -> ShockResult:
        """Propagate a shock through the asset universe and return affected profiles."""

        result = ShockResult(shock=shock)
        affected: Dict[str, ShockedProfile] = {}

        # Step 1: Apply direct shock to source
        if shock.source_asset in profiles:
            source_profile = self._apply_shock(
                shock.source_asset, profiles[shock.source_asset], shock, shock.source_severity, 0
            )
            source_profile.is_directly_affected = True
            affected[shock.source_asset] = source_profile

        # Step 2: Propagate through correlation network
        if shock.propagation != ShockPropagation.NONE and shock.related_assets:
            visited: Set[str] = {shock.source_asset}
            current: Dict[str, float] = {
                a: shock.source_severity
                for a in shock.related_assets
                if a in profiles
            }

            for hop in range(1, shock.max_hops + 1):
                if not current:
                    break

                next_wave: Dict[str, float] = {}
                for asset, severity in current.items():
                    if asset in visited:
                        continue
                    visited.add(asset)

                    # Compute propagated severity
                    propagated = severity * shock.contagion_decay
                    if shock.source_asset in self._correlations:
                        corr = self._correlations[shock.source_asset].get(asset, 0.0)
                        propagated *= max(0.1, abs(corr))

                    if asset in profiles:
                        sp = self._apply_shock(asset, profiles[asset], shock, propagated, hop)
                        affected[asset] = sp

                    # Find next hop: assets correlated with this one
                    if shock.propagation in (ShockPropagation.CASCADING, ShockPropagation.INDIRECT):
                        for next_asset, corr in self._correlations.get(asset, {}).items():
                            if next_asset not in visited and next_asset in profiles:
                                next_wave[next_asset] = severity * shock.contagion_decay * abs(corr)

                current = next_wave

        # Step 3: Compute systemic metrics
        result.affected_assets = list(affected.values())
        result.total_assets_affected = len(affected)

        if affected:
            result.systemic_severity = sum(
                a.severity_received for a in affected.values()
            ) / len(affected)

        # Detect regime shift
        avg_score = (
            sum(a.shocked_liquidity_score for a in affected.values()) / len(affected)
            if affected else 50.0
        )
        if avg_score < 20:
            result.new_regime = "CRISIS"
            result.regime_shift_detected = True
        elif avg_score < 40:
            result.new_regime = "STRESSED"
            result.regime_shift_detected = True
        elif avg_score < 60:
            result.new_regime = "LOW_LIQUIDITY"
            result.regime_shift_detected = True
        else:
            result.new_regime = "NORMAL"

        return result

    @staticmethod
    def _apply_shock(asset: str,
                      profile: LiquidityProfile,
                      shock: LiquidityShock,
                      severity: float,
                      hop: int) -> ShockedProfile:
        """Apply shock multipliers to a single profile."""
        vol_drop = shock.volume_drop_pct * severity
        spread_widen = 1.0 + (shock.spread_widening_x - 1.0) * severity
        depth_drop = shock.depth_drop_pct * severity
        vol_spike = 1.0 + (shock.volatility_spike_x - 1.0) * severity

        sp = ShockedProfile(
            asset=asset,
            original_profile=profile,
            shock=shock,
            propagation_hop=hop,
            severity_received=severity,
            shocked_volume=profile.avg_daily_volume * (1.0 - vol_drop),
            shocked_spread_bps=profile.spread_bps * spread_widen,
            shocked_depth=profile.depth * (1.0 - depth_drop),
            shocked_volatility=profile.volatility * vol_spike,
        )

        # Compute shocked liquidity score (simplified)
        volume_score = max(0, 30 * sp.shocked_volume / max(profile.avg_daily_volume, 1))
        if sp.shocked_spread_bps > 0:
            spread_score = max(0, 25 * profile.spread_bps / sp.shocked_spread_bps)
        else:
            spread_score = 25
        depth_score = max(0, 20 * sp.shocked_depth / max(profile.depth, 1))
        vol_penalty = max(0, 15 * (sp.shocked_volatility / max(profile.volatility, 0.01) - 1))

        sp.shocked_liquidity_score = max(0, volume_score + spread_score + depth_score + 15 - vol_penalty)
        return sp


# ── Pre-defined shocks ────────────────────────────────────────────

PREDEFINED_SHOCKS: Dict[str, LiquidityShock] = {
    "earnings_surprise": LiquidityShock(
        shock_type=ShockType.SINGLE_ASSET,
        propagation=ShockPropagation.DIRECT,
        volume_drop_pct=0.30,
        spread_widening_x=3.0,
        depth_drop_pct=0.40,
        volatility_spike_x=2.0,
        contagion_decay=0.3,
    ),
    "sector_rotation": LiquidityShock(
        shock_type=ShockType.SECTOR_WIDE,
        propagation=ShockPropagation.INDIRECT,
        volume_drop_pct=0.20,
        spread_widening_x=1.5,
        depth_drop_pct=0.25,
        contagion_decay=0.5,
        max_hops=2,
    ),
    "correlation_cascade": LiquidityShock(
        shock_type=ShockType.CORRELATION_DRIVEN,
        propagation=ShockPropagation.CASCADING,
        volume_drop_pct=0.35,
        spread_widening_x=4.0,
        depth_drop_pct=0.50,
        volatility_spike_x=3.0,
        contagion_decay=0.6,
        max_hops=3,
    ),
    "market_meltdown": LiquidityShock(
        shock_type=ShockType.MARKET_WIDE,
        propagation=ShockPropagation.CASCADING,
        volume_drop_pct=0.50,
        spread_widening_x=8.0,
        depth_drop_pct=0.70,
        volatility_spike_x=4.0,
        contagion_decay=0.8,
        max_hops=5,
    ),
    "systemic_event": LiquidityShock(
        shock_type=ShockType.SYSTEMIC,
        propagation=ShockPropagation.CASCADING,
        volume_drop_pct=0.70,
        spread_widening_x=15.0,
        depth_drop_pct=0.85,
        volatility_spike_x=6.0,
        contagion_decay=0.9,
        max_hops=10,
    ),
}
