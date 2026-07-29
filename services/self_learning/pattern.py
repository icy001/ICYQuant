"""Pattern Discovery Engine - discovers market and trading patterns."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict


class PatternType(Enum):
    """Type of pattern discovered."""
    MARKET = "MARKET"
    TRADING = "TRADING"
    RISK = "RISK"
    STRATEGY = "STRATEGY"
    REGIME = "REGIME"
    CORRELATION = "CORRELATION"


class PatternStrength(Enum):
    """Strength/confidence of a discovered pattern."""
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    CONFIRMED = "CONFIRMED"


class PatternCategory(Enum):
    """Category of pattern."""
    TREND = "TREND"
    REVERSAL = "REVERSAL"
    MOMENTUM = "MOMENTUM"
    VOLATILITY = "VOLATILITY"
    SEASONAL = "SEASONAL"
    REGIME_SWITCH = "REGIME_SWITCH"
    CORRELATION_CLUSTER = "CORRELATION_CLUSTER"
    ANOMALY = "ANOMALY"


@dataclass
class DiscoveredPattern:
    """A single discovered pattern."""
    pattern_id: str
    name: str
    pattern_type: PatternType
    category: PatternCategory
    description: str
    confidence: float
    strength: PatternStrength
    occurrence_count: int
    features: Dict[str, Any]
    context: Dict[str, Any]
    actionable: bool
    trade_implication: str
    supporting_evidence: List[str] = field(default_factory=list)

    def is_tradeable(self) -> bool:
        return self.actionable and self.strength in (
            PatternStrength.STRONG, PatternStrength.CONFIRMED)


@dataclass
class PatternCluster:
    """A cluster of related patterns."""
    cluster_id: str
    name: str
    patterns: List[DiscoveredPattern]
    theme: str
    confidence: float

    @property
    def actionable_patterns(self) -> List[DiscoveredPattern]:
        return [p for p in self.patterns if p.is_tradeable()]


class PatternDiscoveryEngine:
    """Pattern Discovery Engine.

    Discovers patterns in:
    - Market data (trends, regimes, correlations)
    - Trading data (behavioral patterns, strategy patterns)
    - Risk data (volatility clusters, drawdown patterns)

    Example pattern discovery:
    Fed Cut Cycle + AI Bubble + Liquidity Expansion
    -> Technology Rally Pattern
    """

    def __init__(self):
        self.patterns: List[DiscoveredPattern] = []
        self.clusters: List[PatternCluster] = []
        self._pattern_counter = 0

    def discover(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Discover patterns from data.

        Args:
            data: Input data for pattern discovery.

        Returns:
            Dict with discovered patterns.
        """
        discovered = []

        # Market patterns
        if "market_data" in data:
            market_patterns = self._discover_market_patterns(data["market_data"])
            discovered.extend(market_patterns)

        # Trading patterns
        if "trading_data" in data:
            trading_patterns = self._discover_trading_patterns(data["trading_data"])
            discovered.extend(trading_patterns)

        # Risk patterns
        if "risk_data" in data:
            risk_patterns = self._discover_risk_patterns(data["risk_data"])
            discovered.extend(risk_patterns)

        # Strategy patterns
        if "strategy_data" in data:
            strategy_patterns = self._discover_strategy_patterns(data["strategy_data"])
            discovered.extend(strategy_patterns)

        self.patterns.extend(discovered)

        # Cluster related patterns
        clusters = self._cluster_patterns(discovered)
        self.clusters.extend(clusters)

        return {
            "patterns_found": len(discovered),
            "clusters_formed": len(clusters),
            "patterns": [
                {
                    "id": p.pattern_id,
                    "name": p.name,
                    "type": p.pattern_type.value,
                    "category": p.category.value,
                    "strength": p.strength.value,
                    "confidence": p.confidence,
                    "actionable": p.actionable,
                    "trade_implication": p.trade_implication,
                }
                for p in discovered
            ],
            "clusters": [
                {
                    "id": c.cluster_id,
                    "name": c.name,
                    "theme": c.theme,
                    "pattern_count": len(c.patterns),
                    "actionable_count": len(c.actionable_patterns),
                }
                for c in clusters
            ],
        }

    def query(self, filters: Dict[str, Any] = None) -> List[DiscoveredPattern]:
        """Query discovered patterns with filters.

        Args:
            filters: Optional dict of filter criteria.

        Returns:
            Filtered list of patterns.
        """
        results = self.patterns
        if filters is None:
            return results

        if "type" in filters:
            results = [p for p in results
                       if p.pattern_type.value == filters["type"]]
        if "category" in filters:
            results = [p for p in results
                       if p.category.value == filters["category"]]
        if "strength" in filters:
            results = [p for p in results
                       if p.strength.value == filters["strength"]]
        if "min_confidence" in filters:
            results = [p for p in results
                       if p.confidence >= filters["min_confidence"]]
        if "actionable_only" in filters and filters["actionable_only"]:
            results = [p for p in results if p.is_tradeable()]
        if "name_contains" in filters:
            query_str = filters["name_contains"].lower()
            results = [p for p in results
                       if query_str in p.name.lower()]

        return results

    def get_tradeable_patterns(self) -> List[DiscoveredPattern]:
        """Get all tradeable (strong enough) patterns.

        Returns:
            List of tradeable patterns.
        """
        return [p for p in self.patterns if p.is_tradeable()]

    def get_statistics(self) -> Dict[str, Any]:
        """Get pattern discovery statistics.

        Returns:
            Dict with statistics.
        """
        if not self.patterns:
            return {"total_patterns": 0}

        by_type = defaultdict(int)
        by_category = defaultdict(int)
        by_strength = defaultdict(int)

        for p in self.patterns:
            by_type[p.pattern_type.value] += 1
            by_category[p.category.value] += 1
            by_strength[p.strength.value] += 1

        return {
            "total_patterns": len(self.patterns),
            "total_clusters": len(self.clusters),
            "tradeable_patterns": len(self.get_tradeable_patterns()),
            "by_type": dict(by_type),
            "by_category": dict(by_category),
            "by_strength": dict(by_strength),
            "avg_confidence": sum(p.confidence for p in self.patterns) / max(len(self.patterns), 1),
        }

    # ---- Internal pattern discovery methods ----

    def _discover_market_patterns(self, data: Dict[str, Any]) -> List[DiscoveredPattern]:
        patterns = []
        trend = data.get("trend", 0.0)
        volatility = data.get("volatility", 0.15)
        regime = data.get("regime", "normal")

        if trend > 0.02:
            p = self._create_pattern(
                name="Bullish Trend Pattern",
                ptype=PatternType.MARKET,
                category=PatternCategory.TREND,
                description=f"Strong upward trend detected (trend={trend:.3f})",
                confidence=min(0.9, abs(trend) * 20),
                strength=PatternStrength.STRONG if abs(trend) > 0.03 else PatternStrength.MODERATE,
                features={"trend": trend, "regime": regime},
                context={"market_phase": "bullish"},
                trade_implication="Favor long positions, trend-following strategies",
            )
            patterns.append(p)
        elif trend < -0.02:
            p = self._create_pattern(
                name="Bearish Trend Pattern",
                ptype=PatternType.MARKET,
                category=PatternCategory.TREND,
                description=f"Strong downward trend detected (trend={trend:.3f})",
                confidence=min(0.9, abs(trend) * 20),
                strength=PatternStrength.STRONG if abs(trend) > 0.03 else PatternStrength.MODERATE,
                features={"trend": trend, "regime": regime},
                context={"market_phase": "bearish"},
                trade_implication="Reduce long exposure, consider hedging",
            )
            patterns.append(p)

        if volatility > 0.30:
            p = self._create_pattern(
                name="High Volatility Regime",
                ptype=PatternType.MARKET,
                category=PatternCategory.VOLATILITY,
                description=f"Elevated volatility (vol={volatility:.3f})",
                confidence=min(0.85, volatility),
                strength=PatternStrength.STRONG if volatility > 0.40 else PatternStrength.MODERATE,
                features={"volatility": volatility, "regime": regime},
                context={"market_phase": "high_vol"},
                trade_implication="Reduce position sizes, widen stops",
            )
            patterns.append(p)

        if regime == "transition":
            p = self._create_pattern(
                name="Regime Transition Pattern",
                ptype=PatternType.REGIME,
                category=PatternCategory.REGIME_SWITCH,
                description="Market regime in transition",
                confidence=0.6,
                strength=PatternStrength.MODERATE,
                features={"regime": regime},
                context={"market_phase": "transition"},
                trade_implication="Reduce conviction, wait for regime confirmation",
            )
            patterns.append(p)

        return patterns

    def _discover_trading_patterns(self, data: Dict[str, Any]) -> List[DiscoveredPattern]:
        patterns = []
        win_rate = data.get("win_rate", 0.5)
        trades_count = data.get("trades_count", 0)
        avg_win = data.get("avg_win", 0.0)
        avg_loss = data.get("avg_loss", 0.0)

        if trades_count >= 10 and win_rate > 0.6:
            p = self._create_pattern(
                name="High Win Rate Pattern",
                ptype=PatternType.TRADING,
                category=PatternCategory.MOMENTUM,
                description=f"Consistent high win rate ({win_rate:.1%})",
                confidence=min(0.9, win_rate + trades_count * 0.01),
                strength=PatternStrength.STRONG if win_rate > 0.7 else PatternStrength.MODERATE,
                features={"win_rate": win_rate, "trades": trades_count},
                context={"strategy_state": "performing"},
                trade_implication="Maintain current strategy parameters",
            )
            patterns.append(p)

        if trades_count >= 10 and win_rate < 0.4:
            p = self._create_pattern(
                name="Low Win Rate Pattern",
                ptype=PatternType.TRADING,
                category=PatternCategory.MOMENTUM,
                description=f"Persistent low win rate ({win_rate:.1%})",
                confidence=min(0.85, (1 - win_rate) + trades_count * 0.01),
                strength=PatternStrength.STRONG if win_rate < 0.35 else PatternStrength.MODERATE,
                features={"win_rate": win_rate, "trades": trades_count},
                context={"strategy_state": "struggling"},
                trade_implication="Review entry criteria, consider strategy modification",
            )
            patterns.append(p)

        if avg_win > 0 and avg_loss < 0 and (avg_win / max(abs(avg_loss), 0.0001)) > 2.0:
            p = self._create_pattern(
                name="Favorable Risk-Reward Pattern",
                ptype=PatternType.TRADING,
                category=PatternCategory.MOMENTUM,
                description=f"Win/loss ratio > 2:1 (win={avg_win:.4f}, loss={avg_loss:.4f})",
                confidence=0.8,
                strength=PatternStrength.STRONG,
                features={"avg_win": avg_win, "avg_loss": avg_loss},
                context={"strategy_state": "efficient"},
                trade_implication="Scale up position sizing on high-confidence setups",
            )
            patterns.append(p)

        return patterns

    def _discover_risk_patterns(self, data: Dict[str, Any]) -> List[DiscoveredPattern]:
        patterns = []
        max_drawdown = data.get("max_drawdown", 0.0)
        var_95 = data.get("var_95", 0.0)
        concentration = data.get("concentration", 0.0)

        if abs(max_drawdown) > 0.15:
            p = self._create_pattern(
                name="Deep Drawdown Pattern",
                ptype=PatternType.RISK,
                category=PatternCategory.VOLATILITY,
                description=f"Significant drawdown detected (DD={abs(max_drawdown):.1%})",
                confidence=min(0.9, abs(max_drawdown) * 3),
                strength=PatternStrength.STRONG if abs(max_drawdown) > 0.25 else PatternStrength.MODERATE,
                features={"max_drawdown": max_drawdown},
                context={"risk_level": "elevated"},
                trade_implication="Implement drawdown protection rules",
            )
            patterns.append(p)

        if concentration > 0.4:
            p = self._create_pattern(
                name="High Concentration Risk",
                ptype=PatternType.RISK,
                category=PatternCategory.CORRELATION_CLUSTER,
                description=f"Portfolio concentration is high ({concentration:.1%})",
                confidence=min(0.85, concentration + 0.2),
                strength=PatternStrength.STRONG if concentration > 0.6 else PatternStrength.MODERATE,
                features={"concentration": concentration},
                context={"risk_level": "concentrated"},
                trade_implication="Diversify holdings, reduce position overlap",
            )
            patterns.append(p)

        if abs(var_95) > 0.03:
            p = self._create_pattern(
                name="Elevated Tail Risk",
                ptype=PatternType.RISK,
                category=PatternCategory.VOLATILITY,
                description=f"VaR 95% is elevated (VaR={abs(var_95):.3f})",
                confidence=0.75,
                strength=PatternStrength.MODERATE,
                features={"var_95": var_95},
                context={"risk_level": "tail_risk"},
                trade_implication="Consider tail risk hedging strategies",
            )
            patterns.append(p)

        return patterns

    def _discover_strategy_patterns(self, data: Dict[str, Any]) -> List[DiscoveredPattern]:
        patterns = []
        sharpe = data.get("sharpe", 0.0)
        consistency = data.get("consistency", 0.0)
        regime_performance = data.get("regime_performance", {})

        if sharpe > 1.5:
            p = self._create_pattern(
                name="Excellent Risk-Adjusted Returns",
                ptype=PatternType.STRATEGY,
                category=PatternCategory.MOMENTUM,
                description=f"High Sharpe ratio ({sharpe:.2f})",
                confidence=min(0.9, sharpe / 3),
                strength=PatternStrength.STRONG if sharpe > 2.0 else PatternStrength.MODERATE,
                features={"sharpe": sharpe},
                context={"strategy_quality": "excellent"},
                trade_implication="Increase capital allocation to this strategy",
            )
            patterns.append(p)

        if consistency > 0.7:
            p = self._create_pattern(
                name="Consistent Performance Pattern",
                ptype=PatternType.STRATEGY,
                category=PatternCategory.MOMENTUM,
                description=f"Highly consistent returns (consistency={consistency:.1%})",
                confidence=consistency,
                strength=PatternStrength.STRONG if consistency > 0.85 else PatternStrength.MODERATE,
                features={"consistency": consistency},
                context={"strategy_quality": "reliable"},
                trade_implication="Strategy is reliable - suitable for core allocation",
            )
            patterns.append(p)

        # Regime-specific patterns
        for regime, perf in regime_performance.items():
            if isinstance(perf, dict):
                regime_return = perf.get("return", 0.0)
                if abs(regime_return) > 0.05:
                    direction = "Bullish" if regime_return > 0 else "Bearish"
                    p = self._create_pattern(
                        name=f"{direction} {regime} Regime Pattern",
                        ptype=PatternType.REGIME,
                        category=PatternCategory.REGIME_SWITCH,
                        description=f"Strategy performs {direction.lower()} in {regime} regime",
                        confidence=min(0.85, abs(regime_return) * 5),
                        strength=PatternStrength.MODERATE,
                        features={"regime": regime, "return": regime_return},
                        context={"regime_performance": perf},
                        trade_implication=f"{'Increase' if regime_return > 0 else 'Reduce'} exposure in {regime} regime",
                    )
                    patterns.append(p)

        return patterns

    def _create_pattern(self, name: str, ptype: PatternType,
                        category: PatternCategory, description: str,
                        confidence: float, strength: PatternStrength,
                        features: Dict, context: Dict,
                        trade_implication: str) -> DiscoveredPattern:
        self._pattern_counter += 1
        return DiscoveredPattern(
            pattern_id=f"PTN_{self._pattern_counter:04d}",
            name=name,
            pattern_type=ptype,
            category=category,
            description=description,
            confidence=min(confidence, 1.0),
            strength=strength,
            occurrence_count=1,
            features=features,
            context=context,
            actionable=strength in (PatternStrength.STRONG, PatternStrength.CONFIRMED),
            trade_implication=trade_implication,
        )

    def _cluster_patterns(self, patterns: List[DiscoveredPattern]) -> List[PatternCluster]:
        """Group related patterns into clusters by theme."""
        clusters = []
        if not patterns:
            return clusters

        # Simple theme-based clustering
        trend_patterns = [p for p in patterns if p.category == PatternCategory.TREND]
        if trend_patterns:
            clusters.append(PatternCluster(
                cluster_id=f"CLS_{len(self.clusters):03d}",
                name="Trend Regime Cluster",
                patterns=trend_patterns,
                theme="Market trend and direction signals",
                confidence=sum(p.confidence for p in trend_patterns) / len(trend_patterns),
            ))

        risk_patterns = [p for p in patterns
                         if p.category in (PatternCategory.VOLATILITY, PatternCategory.CORRELATION_CLUSTER)]
        if risk_patterns:
            clusters.append(PatternCluster(
                cluster_id=f"CLS_{len(self.clusters) + 1:03d}",
                name="Risk Environment Cluster",
                patterns=risk_patterns,
                theme="Risk and volatility conditions",
                confidence=sum(p.confidence for p in risk_patterns) / len(risk_patterns),
            ))

        momentum_patterns = [p for p in patterns if p.category == PatternCategory.MOMENTUM]
        if momentum_patterns:
            clusters.append(PatternCluster(
                cluster_id=f"CLS_{len(self.clusters) + 2:03d}",
                name="Momentum & Performance Cluster",
                patterns=momentum_patterns,
                theme="Strategy momentum and performance signals",
                confidence=sum(p.confidence for p in momentum_patterns) / len(momentum_patterns),
            ))

        return clusters
