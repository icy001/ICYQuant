"""Cross Asset Relationship Model.

Defines the asset relationship graph, node types, correlation structures,
and cross-asset signal data models for global multi-asset analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AssetClass(str, Enum):
    """Global asset class taxonomy."""

    EQUITY = "equity"
    EQUITY_SECTOR = "equity_sector"
    EQUITY_GROWTH = "equity_growth"
    EQUITY_VALUE = "equity_value"
    BOND_GOVERNMENT = "bond_government"
    BOND_CORPORATE = "bond_corporate"
    BOND_HIGH_YIELD = "bond_high_yield"
    BOND_TIPS = "bond_tips"
    CURRENCY_MAJOR = "currency_major"
    CURRENCY_EM = "currency_em"
    COMMODITY_PRECIOUS = "commodity_precious"
    COMMODITY_ENERGY = "commodity_energy"
    COMMODITY_INDUSTRIAL = "commodity_industrial"
    COMMODITY_AGRICULTURAL = "commodity_agriculture"
    CRYPTO_MAJOR = "crypto_major"
    CRYPTO_ALT = "crypto_alt"
    REAL_ESTATE = "real_estate"
    CASH = "cash"


class RelationshipType(str, Enum):
    """Type of relationship between two assets."""

    STRONG_POSITIVE = "strong_positive"
    MODERATE_POSITIVE = "moderate_positive"
    WEAK_POSITIVE = "weak_positive"
    UNCORRELATED = "uncorrelated"
    WEAK_NEGATIVE = "weak_negative"
    MODERATE_NEGATIVE = "moderate_negative"
    STRONG_NEGATIVE = "strong_negative"
    CAUSAL_A_TO_B = "causal_a_to_b"
    CAUSAL_B_TO_A = "causal_b_to_a"
    LEAD_LAG = "lead_lag"


class RiskRegime(str, Enum):
    """Cross-asset risk regime classification."""

    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    FLIGHT_TO_QUALITY = "flight_to_quality"
    FLIGHT_TO_CASH = "flight_to_cash"
    INFLATION_HEDGE = "inflation_hedge"
    DEFLATION_HEDGE = "deflation_hedge"
    NORMAL = "normal"


class DollarTrend(str, Enum):
    """Dollar trend classification."""

    STRONG_APPRECIATION = "strong_appreciation"
    APPRECIATION = "appreciation"
    STABLE = "stable"
    DEPRECIATION = "depreciation"
    STRONG_DEPRECIATION = "strong_depreciation"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class AssetRelationship:
    """A pairwise relationship between two assets.

    Attributes:
        asset_a: First asset identifier.
        asset_b: Second asset identifier.
        correlation: Pearson correlation coefficient [-1.0, 1.0].
        relationship_type: Classified relationship type.
        confidence: Relationship confidence [0.0, 1.0].
        window: Lookback window in days used for computation.
        timestamp: When the relationship was computed.
        metadata: Additional metadata.
        class_a: Asset class of asset_a.
        class_b: Asset class of asset_b.
    """

    asset_a: str
    asset_b: str
    correlation: float = 0.0
    relationship_type: RelationshipType = RelationshipType.UNCORRELATED
    confidence: float = 0.5
    window: int = 60
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    class_a: AssetClass | None = None
    class_b: AssetClass | None = None

    def __post_init__(self) -> None:
        if self.correlation < -1.0:
            self.correlation = -1.0
        elif self.correlation > 1.0:
            self.correlation = 1.0

    @property
    def is_positive(self) -> bool:
        return self.correlation > 0.1

    @property
    def is_negative(self) -> bool:
        return self.correlation < -0.1

    @property
    def is_strong(self) -> bool:
        return abs(self.correlation) >= 0.7

    @property
    def is_significant(self) -> bool:
        return self.confidence >= 0.5 and abs(self.correlation) >= 0.3


@dataclass
class AssetNode:
    """A node in the cross-asset relationship graph.

    Attributes:
        asset: Asset identifier.
        asset_class: Asset class classification.
        relationships: Outgoing relationships from this node.
        weight: Node importance weight.
        metadata: Additional asset metadata.
    """

    asset: str
    asset_class: AssetClass = AssetClass.EQUITY
    relationships: list[AssetRelationship] = field(default_factory=list)
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def degree(self) -> int:
        return len(self.relationships)

    @property
    def positive_count(self) -> int:
        return sum(1 for r in self.relationships if r.is_positive)

    @property
    def negative_count(self) -> int:
        return sum(1 for r in self.relationships if r.is_negative)


@dataclass
class RelationshipGraph:
    """Complete cross-asset relationship graph.

    Attributes:
        nodes: All asset nodes in the graph.
        edges: All relationships as edges.
        timestamp: Graph construction timestamp.
        metadata: Graph-level metadata.
    """

    nodes: dict[str, AssetNode] = field(default_factory=dict)
    edges: list[AssetRelationship] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def get_node(self, asset: str) -> AssetNode | None:
        return self.nodes.get(asset)

    def get_relationships(self, asset: str) -> list[AssetRelationship]:
        node = self.nodes.get(asset)
        return node.relationships if node else []

    def get_related_assets(self, asset: str, min_corr: float = 0.3) -> list[str]:
        node = self.nodes.get(asset)
        if not node:
            return []
        return [r.asset_b for r in node.relationships if abs(r.correlation) >= min_corr]

    def get_best_hedge(self, asset: str) -> AssetRelationship | None:
        """Find the best hedging asset (most negative correlation)."""
        node = self.nodes.get(asset)
        if not node:
            return None
        negatives = [r for r in node.relationships if r.is_negative]
        return min(negatives, key=lambda r: r.correlation) if negatives else None


@dataclass
class CrossAssetSignal:
    """A signal derived from cross-asset relationship analysis.

    Attributes:
        signal_id: Unique signal identifier.
        asset: Target asset.
        signal_type: Type of cross-asset signal.
        value: Signal value.
        direction: Expected direction (1=bullish, -1=bearish, 0=neutral).
        confidence: Signal confidence [0.0, 1.0].
        trigger_assets: Assets that triggered this signal.
        description: Human-readable description.
        timestamp: Signal generation time.
        horizon: Expected horizon in days.
        metadata: Additional context.
    """

    signal_id: str
    asset: str
    signal_type: str
    value: float = 0.0
    direction: int = 0
    confidence: float = 0.5
    trigger_assets: list[str] = field(default_factory=list)
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    horizon: int = 5
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        return self.confidence >= 0.5 and self.direction != 0

    @property
    def absolute_strength(self) -> float:
        return abs(self.value) * self.confidence
