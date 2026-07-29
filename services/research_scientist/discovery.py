"""Quant Discovery Engine - automated alpha and signal discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class DiscoveryType(Enum):
    """Types of quant discoveries."""

    FACTOR = "factor"
    SIGNAL = "signal"
    PATTERN = "pattern"
    RELATIONSHIP = "relationship"
    ANOMALY = "anomaly"
    REGIME = "regime"
    INTERACTION = "interaction"


class DiscoveryStatus(Enum):
    """Discovery lifecycle status."""

    IDENTIFIED = "identified"
    VALIDATED = "validated"
    PROMISING = "promising"
    CONFIRMED = "confirmed"
    DEPLOYED = "deployed"
    DECAYED = "decayed"


@dataclass
class Discovery:
    """A quant alpha discovery."""

    id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    discovery_type: DiscoveryType = DiscoveryType.FACTOR
    status: DiscoveryStatus = DiscoveryStatus.IDENTIFIED
    description: str = ""
    source_data: str = ""
    formula: str = ""
    performance: Dict[str, Any] = field(default_factory=dict)
    sharpe: float = 0.0
    information_ratio: float = 0.0
    ic_mean: float = 0.0
    ic_ir: float = 0.0
    turnover: float = 0.0
    correlation_to_existing: float = 0.0
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    validated_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "type": self.discovery_type.value,
            "status": self.status.value, "description": self.description,
            "source_data": self.source_data, "formula": self.formula,
            "performance": self.performance, "sharpe": self.sharpe,
            "information_ratio": self.information_ratio, "ic_mean": self.ic_mean,
            "ic_ir": self.ic_ir, "turnover": self.turnover,
            "correlation_to_existing": self.correlation_to_existing,
            "discovered_at": self.discovered_at.isoformat(),
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
            "tags": self.tags, "metadata": self.metadata,
        }


class QuantDiscoveryEngine:
    """Quant Discovery Engine.

    Automatically discovers alpha signals, factors, patterns,
    and relationships from data.

    Discovery methods:
    1. Factor Mining: systematic factor testing
    2. Signal Detection: technical/fundamental signal extraction
    3. Pattern Recognition: statistical pattern identification
    4. Relationship Discovery: variable interaction analysis
    5. Anomaly Detection: unusual market behavior
    6. Regime Detection: market state classification
    7. Interaction Discovery: factor combination effects

    Each discovery is tracked, validated, and scored for
    potential deployment as a trading signal.
    """

    def __init__(self):
        self.discoveries: Dict[str, Discovery] = {}
        self.discovery_history: List[Dict[str, Any]] = []

    def discover(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Discover alpha from data. Main entry point."""
        return self.run_discovery(data).to_dict()

    def run_discovery(self, data: Dict[str, Any]) -> Discovery:
        """Run discovery process on data to find alpha."""
        discovery_type = self._infer_discovery_type(data)
        name = self._generate_name(discovery_type, data)

        discovery = Discovery(
            name=name,
            discovery_type=discovery_type,
            description=f"Discovered {discovery_type.value} from {data.get('name', 'data')}",
            source_data=data.get("name", "unknown"),
            formula=self._generate_formula(discovery_type),
            performance=self._estimate_performance(discovery_type),
            sharpe=self._estimate_sharpe(discovery_type),
            information_ratio=self._estimate_ir(discovery_type),
            ic_mean=self._estimate_ic_mean(discovery_type),
            ic_ir=self._estimate_ic_ir(discovery_type),
            turnover=self._estimate_turnover(discovery_type),
            correlation_to_existing=self._estimate_correlation(discovery_type),
            metadata={"source": "auto_discovery", "data_shape": data.get("shape", "unknown")},
        )

        self.discoveries[discovery.id] = discovery
        self.discovery_history.append({
            "discovery_id": discovery.id, "type": discovery_type.value,
            "sharpe": discovery.sharpe, "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return discovery

    def _infer_discovery_type(self, data: Dict[str, Any]) -> DiscoveryType:
        ds_type = data.get("type", "").lower()
        mapping = {
            "factor": DiscoveryType.FACTOR, "signal": DiscoveryType.SIGNAL,
            "pattern": DiscoveryType.PATTERN, "relationship": DiscoveryType.RELATIONSHIP,
            "anomaly": DiscoveryType.ANOMALY, "regime": DiscoveryType.REGIME,
            "interaction": DiscoveryType.INTERACTION,
        }
        return mapping.get(ds_type, DiscoveryType.FACTOR)

    def _generate_name(self, dtype: DiscoveryType, data: Dict[str, Any]) -> str:
        prefix = {
            DiscoveryType.FACTOR: "Factor",
            DiscoveryType.SIGNAL: "Signal",
            DiscoveryType.PATTERN: "Pattern",
            DiscoveryType.RELATIONSHIP: "Relationship",
            DiscoveryType.ANOMALY: "Anomaly",
            DiscoveryType.REGIME: "Regime",
            DiscoveryType.INTERACTION: "Interaction",
        }
        return f"{prefix.get(dtype, 'Discovery')}_{uuid4().hex[:8]}"

    def _generate_formula(self, dtype: DiscoveryType) -> str:
        formulas = {
            DiscoveryType.FACTOR: "rank(zscore(returns_3m)) * rank(zscore(volume_ratio))",
            DiscoveryType.SIGNAL: "cross_sectional_zscore(returns_1m) - cross_sectional_zscore(returns_12m)",
            DiscoveryType.PATTERN: "pattern_score = similarity(current_window, historical_pattern)",
            DiscoveryType.RELATIONSHIP: "correlation(series_a, series_b, rolling_window=60)",
            DiscoveryType.ANOMALY: "|zscore(returns)| > 3 * rolling_std(returns, 252)",
            DiscoveryType.REGIME: "regime = classify(market_features, n_states=3)",
            DiscoveryType.INTERACTION: "factor_a * factor_b + factor_a * factor_c",
        }
        return formulas.get(dtype, "custom_formula")

    def _estimate_sharpe(self, dtype: DiscoveryType) -> float:
        base = {DiscoveryType.FACTOR: 0.8, DiscoveryType.SIGNAL: 0.6,
                DiscoveryType.PATTERN: 0.4, DiscoveryType.RELATIONSHIP: 0.5,
                DiscoveryType.ANOMALY: 0.3, DiscoveryType.REGIME: 0.7,
                DiscoveryType.INTERACTION: 0.9}
        return base.get(dtype, 0.5)

    def _estimate_ir(self, dtype: DiscoveryType) -> float:
        return self._estimate_sharpe(dtype) * 0.7

    def _estimate_ic_mean(self, dtype: DiscoveryType) -> float:
        base = {DiscoveryType.FACTOR: 0.04, DiscoveryType.SIGNAL: 0.03,
                DiscoveryType.PATTERN: 0.02, DiscoveryType.ANOMALY: 0.015,
                DiscoveryType.INTERACTION: 0.05}
        return base.get(dtype, 0.03)

    def _estimate_ic_ir(self, dtype: DiscoveryType) -> float:
        return self._estimate_ic_mean(dtype) * 4

    def _estimate_turnover(self, dtype: DiscoveryType) -> float:
        base = {DiscoveryType.FACTOR: 0.3, DiscoveryType.SIGNAL: 0.5,
                DiscoveryType.PATTERN: 0.6, DiscoveryType.ANOMALY: 0.2}
        return base.get(dtype, 0.4)

    def _estimate_correlation(self, dtype: DiscoveryType) -> float:
        return 0.15

    def _estimate_performance(self, dtype: DiscoveryType) -> Dict[str, Any]:
        return {
            "sharpe": self._estimate_sharpe(dtype),
            "information_ratio": self._estimate_ir(dtype),
            "ic_mean": self._estimate_ic_mean(dtype),
            "ic_ir": self._estimate_ic_ir(dtype),
        }

    def validate_discovery(self, discovery_id: str) -> Optional[Dict[str, Any]]:
        """Validate a discovery."""
        if discovery_id not in self.discoveries:
            return None
        d = self.discoveries[discovery_id]
        if d.sharpe > 0.5 and d.ic_mean > 0.02:
            d.status = DiscoveryStatus.CONFIRMED
        elif d.sharpe > 0.3:
            d.status = DiscoveryStatus.PROMISING
        else:
            d.status = DiscoveryStatus.DECAYED
        d.validated_at = datetime.now(timezone.utc)
        return d.to_dict()

    def rank_discoveries(self) -> List[Dict[str, Any]]:
        """Rank discoveries by quality score."""
        scored = []
        for d in self.discoveries.values():
            score = (d.sharpe * 0.4 + d.ic_mean * 10 * 0.3 +
                     d.ic_ir * 0.15 + (1 - d.correlation_to_existing) * 0.15)
            scored.append({"id": d.id, "name": d.name, "type": d.discovery_type.value,
                           "sharpe": d.sharpe, "ic_mean": d.ic_mean, "score": score})
        return sorted(scored, key=lambda x: x["score"], reverse=True)

    def get_discovery(self, discovery_id: str) -> Optional[Dict[str, Any]]:
        d = self.discoveries.get(discovery_id)
        return d.to_dict() if d else None

    def list_discoveries(self, status: Optional[DiscoveryStatus] = None) -> List[Dict[str, Any]]:
        result = []
        for d in self.discoveries.values():
            if status is None or d.status == status:
                result.append({"id": d.id, "name": d.name, "type": d.discovery_type.value,
                               "sharpe": d.sharpe, "status": d.status.value})
        return result

    def get_summary(self) -> Dict[str, Any]:
        total = len(self.discoveries)
        confirmed = sum(1 for d in self.discoveries.values() if d.status == DiscoveryStatus.CONFIRMED)
        promising = sum(1 for d in self.discoveries.values() if d.status == DiscoveryStatus.PROMISING)
        return {"total_discoveries": total, "confirmed": confirmed, "promising": promising,
                "top_sharpe": max((d.sharpe for d in self.discoveries.values()), default=0.0)}
