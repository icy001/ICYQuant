"""
Liquidity Monitor — Real-time monitoring of liquidity conditions.

Detects liquidity deterioration, spread widening, and volume declines.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class LiquidityAlertType(str, Enum):
    SPREAD_WIDENING = "spread_widening"
    VOLUME_DECLINING = "volume_declining"
    DEPTH_REDUCING = "depth_reducing"
    VOLATILITY_SPIKE = "volatility_spike"
    REGIME_CHANGE = "regime_change"


@dataclass
class LiquidityAlert:
    """Liquidity monitoring alert."""

    alert_id: str = field(default_factory=lambda: f"LA-{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    asset: str = ""
    alert_type: LiquidityAlertType = LiquidityAlertType.SPREAD_WIDENING
    current_value: float = 0.0
    reference_value: float = 0.0
    change_pct: float = 0.0
    severity: str = "WARNING"
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "asset": self.asset,
            "type": self.alert_type.value,
            "change_pct": self.change_pct,
            "severity": self.severity,
            "message": self.message,
        }


class LiquidityMonitor:
    """Monitors liquidity conditions and generates alerts."""

    def __init__(self):
        self._baselines: Dict[str, Dict[str, float]] = {}  # asset -> {metric: baseline}
        self._alerts: List[LiquidityAlert] = []
        self._thresholds = {
            "spread": 0.50,      # 50% widening
            "volume": -0.30,      # 30% decline
            "depth": -0.40,       # 40% depth reduction
            "volatility": 0.50,   # 50% volatility spike
        }

    def set_baseline(self, asset: str, spread_bps: float, volume: float, depth: float, volatility: float) -> None:
        self._baselines[asset] = {
            "spread": spread_bps, "volume": volume, "depth": depth, "volatility": volatility,
        }

    def check(self, asset: str, spread_bps: float, volume: float, depth: float, volatility: float) -> List[LiquidityAlert]:
        """Check current values against baselines."""
        baseline = self._baselines.get(asset)
        alerts = []

        if baseline:
            # Spread widening
            if baseline["spread"] > 0:
                change = (spread_bps - baseline["spread"]) / baseline["spread"]
                if change > self._thresholds["spread"]:
                    alert = LiquidityAlert(asset=asset, alert_type=LiquidityAlertType.SPREAD_WIDENING,
                        current_value=spread_bps, reference_value=baseline["spread"],
                        change_pct=change, severity="CRITICAL" if change > 1.0 else "WARNING",
                        message=f"Spread widened {change:.0%}: {spread_bps:.1f} bps")
                    alerts.append(alert)

            # Volume declining
            if baseline["volume"] > 0:
                change = (volume - baseline["volume"]) / baseline["volume"]
                if change < self._thresholds["volume"]:
                    alert = LiquidityAlert(asset=asset, alert_type=LiquidityAlertType.VOLUME_DECLINING,
                        current_value=volume, reference_value=baseline["volume"],
                        change_pct=change, severity="CRITICAL" if change < -0.50 else "WARNING",
                        message=f"Volume declined {change:.0%}")
                    alerts.append(alert)

            # Depth reducing
            if baseline["depth"] > 0:
                change = (depth - baseline["depth"]) / baseline["depth"]
                if change < self._thresholds["depth"]:
                    alert = LiquidityAlert(asset=asset, alert_type=LiquidityAlertType.DEPTH_REDUCING,
                        current_value=depth, reference_value=baseline["depth"],
                        change_pct=change, severity="WARNING",
                        message=f"Order book depth reduced {change:.0%}")
                    alerts.append(alert)

            # Volatility spike
            if baseline["volatility"] > 0:
                change = (volatility - baseline["volatility"]) / baseline["volatility"]
                if change > self._thresholds["volatility"]:
                    alert = LiquidityAlert(asset=asset, alert_type=LiquidityAlertType.VOLATILITY_SPIKE,
                        current_value=volatility, reference_value=baseline["volatility"],
                        change_pct=change, severity="CRITICAL" if change > 1.0 else "WARNING",
                        message=f"Volatility spiked {change:.0%}")
                    alerts.append(alert)

        self._alerts.extend(alerts)
        return alerts

    def recent_alerts(self, n: int = 50) -> List[LiquidityAlert]:
        return self._alerts[-n:]

    def summary(self) -> Dict[str, Any]:
        if not self._alerts:
            return {"alerts": 0}
        return {
            "total_alerts": len(self._alerts),
            "critical": sum(1 for a in self._alerts[-20:] if a.severity == "CRITICAL"),
            "warning": sum(1 for a in self._alerts[-20:] if a.severity == "WARNING"),
        }
